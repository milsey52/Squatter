"""Debt and bankruptcy: a negative balance blocks rolling until the player
liquidates; debt beyond full liquidation value eliminates the player; the
last active player standing wins."""
import asyncio
import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import main
from app import models
from app.db import SessionLocal
from app.services import ai_autopilot
from app.services.bankruptcy_service import BankruptcyService, InDebtError
from app.services.ledger_service import LedgerService
from app.services.turn_manager import TurnManager
from tests.conftest import drain_cash, total_sheep


def mortgage_all(session, game, name, leave=0):
    paddocks = (
        session.query(models.Paddock)
        .filter_by(game_id=game.game_id, owner_game_player_id=game.players[name])
        .order_by(models.Paddock.paddock_number)
        .all()
    )
    for p in paddocks[leave:]:
        p.is_mortgaged = True
    session.commit()


# ── Liquidation arithmetic ──────────────────────────────────────────────

def test_liquidation_value_counts_all_assets(session, game_factory):
    g = game_factory(sheep_per_paddock=2)  # 10 pens, 5 unmortgaged natural
    jim = session.query(models.GamePlayer).get(g.players["Jim"])
    jim.haystack_pasture = True
    session.commit()
    bk = BankruptcyService(session, g.game_id)
    # 10 pens x $400 + 5 x $100 mortgage + $350 haystack
    assert bk.liquidation_value(g.players["Jim"]) == 4000 + 500 + 350


def test_recovery_boundary(session, game_factory):
    g = game_factory(sheep_per_paddock=0)
    mortgage_all(session, g, "Jim", leave=1)  # one $100 natural mortgage left
    bk = BankruptcyService(session, g.game_id)
    drain_cash(session, g.game_id, g.players["Jim"], 2100)  # balance -100
    assert bk.can_recover(g.players["Jim"])      # -100 + 100 == 0
    drain_cash(session, g.game_id, g.players["Jim"], 100)   # balance -200
    assert not bk.can_recover(g.players["Jim"])  # -200 + 100 < 0


# ── play_turn debt checkpoint ───────────────────────────────────────────

def test_recoverable_debt_blocks_the_roll(session, game_factory):
    g = game_factory(current="Jim")  # 15 pens of sheep = plenty to liquidate
    drain_cash(session, g.game_id, g.players["Jim"], 2700)  # balance -700
    with pytest.raises(InDebtError):
        TurnManager(session, g.game_id).play_turn()
    assert session.query(models.Turn).filter_by(game_id=g.game_id).count() == 0
    assert session.query(models.GamePlayer).get(g.players["Jim"]).is_active


def test_unrecoverable_debt_eliminates_player(session, game_factory):
    g = game_factory(players=(("Hu", False, None), ("Bo", False, None),
                              ("Jim", True, "medium")),
                     sheep_per_paddock=0, current="Jim")
    mortgage_all(session, g, "Jim")
    drain_cash(session, g.game_id, g.players["Jim"], 2600)  # balance -600, nothing left
    # An open pending on Jim must not outlive him.
    turn0 = models.Turn(game_id=g.game_id, turn_number=0,
                        active_game_player_id=g.players["Jim"],
                        dice_roll_1=1, dice_roll_2=1)
    session.add(turn0)
    session.flush()
    stale = models.PendingAction(
        game_id=g.game_id, turn_id=turn0.turn_id, action_type="expense_payment",
        active_player_id=g.players["Jim"], action_data=json.dumps({}))
    session.add(stale)
    session.commit()

    TurnManager(session, g.game_id).play_turn()
    session.commit()

    jim = session.query(models.GamePlayer).get(g.players["Jim"])
    assert not jim.is_active
    assert stale.resolved_at is not None
    # Turn passed to the next active player; game continues (2 left).
    game = session.query(models.Game).get(g.game_id)
    assert game.current_game_player_id == g.players["Hu"]
    assert game.status == "in_progress"
    # The bankruptcy itself is recorded as a no-roll turn.
    bankrupt_turn = (session.query(models.Turn)
                     .filter_by(game_id=g.game_id, active_game_player_id=g.players["Jim"])
                     .order_by(models.Turn.turn_id.desc()).first())
    assert (bankrupt_turn.dice_roll_1, bankrupt_turn.dice_roll_2) == (0, 0)


def test_last_player_standing_wins(session, game_factory):
    g = game_factory(sheep_per_paddock=0, current="Jim")  # Hu + Jim
    mortgage_all(session, g, "Jim")
    drain_cash(session, g.game_id, g.players["Jim"], 2600)

    TurnManager(session, g.game_id).play_turn()
    session.commit()

    game = session.query(models.Game).get(g.game_id)
    assert game.status == "completed"
    won = session.query(models.PendingAction).filter_by(
        game_id=g.game_id, action_type="game_won").one()
    data = json.loads(won.action_data)
    assert data["winner_id"] == g.players["Hu"]
    assert data["reason"] == "last_player_standing"


# ── HTTP route ──────────────────────────────────────────────────────────

def test_route_refuses_roll_with_debt_guidance(session, game_factory):
    g = game_factory(current="Hu")
    drain_cash(session, g.game_id, g.players["Hu"], 2500)  # balance -500
    token = "debt-test-token"
    session.add(models.GameSession(
        session_token=token, user_id=session.query(models.GamePlayer).get(
            g.players["Hu"]).user_id,
        game_id=g.game_id, expires_at=datetime.now() + timedelta(days=1)))
    session.commit()
    client = TestClient(main.app)
    r = client.post(f"/games/{g.game_id}/turns",
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 400
    assert "$500 in debt" in r.json()["detail"]
    assert session.query(models.GamePlayer).get(g.players["Hu"]).is_active


# ── Autopilot debt recovery ─────────────────────────────────────────────

def drive(game_id, monkeypatch):
    async def no_sleep(_delay):
        pass
    monkeypatch.setattr(ai_autopilot.asyncio, "sleep", no_sleep)
    asyncio.run(ai_autopilot._drive_one_game(game_id))


def test_ai_sells_just_enough_sheep_to_clear_debt(session, game_factory, monkeypatch):
    g = game_factory(sheep_per_paddock=3, current="Jim")  # 15 pens: no mortgage rule
    drain_cash(session, g.game_id, g.players["Jim"], 2700)  # balance -700
    drive(g.game_id, monkeypatch)
    session.expire_all()
    # ceil(700/400) = 2 pens sold -> balance +100
    assert total_sheep(session, g.game_id, g.players["Jim"]) == 13
    assert LedgerService(session, g.game_id).player_balance(g.players["Jim"]) == 100
    assert session.query(models.GamePlayer).get(g.players["Jim"]).is_active


def test_ai_sells_haystack_when_no_sheep_or_paddocks(session, game_factory, monkeypatch):
    g = game_factory(sheep_per_paddock=0, current="Jim")
    mortgage_all(session, g, "Jim")
    jim = session.query(models.GamePlayer).get(g.players["Jim"])
    jim.haystack_pasture = True
    session.commit()
    drain_cash(session, g.game_id, g.players["Jim"], 2200)  # balance -200
    drive(g.game_id, monkeypatch)
    session.expire_all()
    jim = session.query(models.GamePlayer).get(g.players["Jim"])
    assert not jim.haystack_pasture
    assert LedgerService(session, g.game_id).player_balance(g.players["Jim"]) == 150
    assert jim.is_active


def test_ai_with_nothing_left_goes_bankrupt_via_autopilot(session, game_factory, monkeypatch):
    g = game_factory(players=(("Hu", False, None), ("Bo", False, None),
                              ("Jim", True, "medium")),
                     sheep_per_paddock=0, current="Jim")
    mortgage_all(session, g, "Jim")
    drain_cash(session, g.game_id, g.players["Jim"], 2600)
    drive(g.game_id, monkeypatch)
    session.expire_all()
    assert not session.query(models.GamePlayer).get(g.players["Jim"]).is_active
    game = session.query(models.Game).get(g.game_id)
    assert game.current_game_player_id == g.players["Hu"]
    assert game.status == "in_progress"


# ── Debt-settlement gate (acknowledge -> settle -> play continues) ──────

def land_on_expense(session, game, cost_flat, monkeypatch):
    """Make the current player land on an expense space costing cost_flat."""
    from app.services.turn_manager import TurnManager
    space = session.query(models.Space).filter_by(board_index=7).one()
    space.space_type = "expense"
    space.cost_flat = cost_flat
    session.commit()
    monkeypatch.setattr(TurnManager, "_roll_dice", staticmethod(lambda: (3, 4)))
    TurnManager(session, game.game_id).play_turn()
    session.commit()


def open_pendings(session, game_id):
    from app.services.decision_service import DecisionService
    return (session.query(models.PendingAction)
            .filter_by(game_id=game_id, resolved_at=None)
            .order_by(models.PendingAction.pending_action_id).all())


def test_debt_gate_orders_acknowledge_then_settle(session, game_factory, spaces, monkeypatch):
    from app.services.decision_service import DecisionService
    g = game_factory(current="Hu")  # $2000 cash, 15 pens (recoverable)
    land_on_expense(session, g, 2300, monkeypatch)  # balance -300

    # Both pendings exist; the expense modal surfaces FIRST.
    pendings = open_pendings(session, g.game_id)
    assert [p.action_type for p in pendings] == ["expense_payment", "debt_settlement"]
    svc = DecisionService(session, g.game_id)
    assert svc.get_pending_action().action_type == "expense_payment"

    # Acknowledge the expense -> the debt gate surfaces next.
    svc.expense_acknowledge(g.players["Hu"])
    session.commit()
    assert svc.get_pending_action().action_type == "debt_settlement"

    # The gate cannot be acknowledged away.
    with pytest.raises(ValueError, match="Debt cannot be acknowledged"):
        svc.acknowledge(g.players["Hu"])

    # Raising cash resolves the gate (here: an emergency-sale credit).
    from app.services.bankruptcy_service import BankruptcyService
    session.add(models.Transaction(
        game_id=g.game_id, player_from_id=None, player_to_id=g.players["Hu"],
        amount=400, transaction_type="emergency_sale"))
    session.flush()
    assert BankruptcyService(session, g.game_id).clear_debt_pending_if_solvent(
        g.players["Hu"])
    session.commit()
    assert svc.get_pending_action() is None  # play continues


def test_debt_gate_blocks_all_rolls(session, game_factory, spaces, monkeypatch):
    from app.services.decision_service import DecisionService
    g = game_factory(players=(("Hu", False, None), ("Bo", False, None)),
                     current="Hu")
    land_on_expense(session, g, 2300, monkeypatch)
    DecisionService(session, g.game_id).expense_acknowledge(g.players["Hu"])
    session.commit()
    # Turn has advanced to Bo, but Hu's open debt gate blocks Bo's roll.
    token = "gate-test-token"
    session.add(models.GameSession(
        session_token=token,
        user_id=session.query(models.GamePlayer).get(g.players["Bo"]).user_id,
        game_id=g.game_id, expires_at=datetime.now() + timedelta(days=1)))
    session.commit()
    client = TestClient(main.app)
    r = client.post(f"/games/{g.game_id}/turns",
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 400
    assert "pending" in r.json()["detail"].lower()


def test_unrecoverable_landing_debt_bankrupts_immediately(session, game_factory, spaces, monkeypatch):
    g = game_factory(players=(("Hu", False, None), ("Bo", False, None),
                              ("Jim", True, "medium")),
                     sheep_per_paddock=0, current="Jim")
    mortgage_all(session, g, "Jim")
    land_on_expense(session, g, 2600, monkeypatch)  # balance -600, nothing to sell

    jim = session.query(models.GamePlayer).get(g.players["Jim"])
    assert not jim.is_active
    # No lingering pendings (the expense modal died with the player).
    assert open_pendings(session, g.game_id) == []
    game = session.query(models.Game).get(g.game_id)
    assert game.current_game_player_id != g.players["Jim"]
    assert game.status == "in_progress"


def test_ai_settles_its_own_debt_gate(session, game_factory, spaces, monkeypatch):
    g = game_factory(sheep_per_paddock=3, current="Jim")  # AI, 15 pens
    land_on_expense(session, g, 2700, monkeypatch)  # balance -700, gate created
    # Resolve the expense modal (the AI autopilot pending branch would do
    # this; resolve directly to isolate the debt-gate behaviour).
    from app.services.decision_service import DecisionService
    DecisionService(session, g.game_id).expense_acknowledge(g.players["Jim"])
    session.commit()

    drive(g.game_id, monkeypatch)  # autopilot tick: AI sells toward solvency
    session.expire_all()
    from app.services.bankruptcy_service import BankruptcyService
    assert BankruptcyService(session, g.game_id).find_open_debt_pending(
        g.players["Jim"]) is None
    assert LedgerService(session, g.game_id).player_balance(g.players["Jim"]) >= 0
