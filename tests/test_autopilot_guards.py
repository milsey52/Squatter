"""Autopilot race guards: the world can change during the pacing sleep
(a human resolves a pending, the turn advances). Every action branch must
re-validate before executing — otherwise the server plays a human's turn.

Technique: replace asyncio.sleep with a coroutine that mutates game state,
recreating exactly the race window the guards close.
"""
import asyncio
import json

import pytest

from app import models
from app.db import SessionLocal
from app.services import ai_autopilot


@pytest.fixture
def game(game_factory, spaces):
    # 15 pens blocks mortgaging (game rule: only at <= 8 pens) and $1500
    # is below the upgrade buffer, so the AI's chosen action is "roll".
    g = game_factory(sheep_per_paddock=3, current="Jim")
    from tests.conftest import drain_cash
    session = SessionLocal()
    drain_cash(session, g.game_id, g.players["Jim"], 500)
    session.close()
    return g


@pytest.fixture
def mortgage_game(game_factory, spaces):
    # 5 pens + $100 cash (< $200 floor): the AI's chosen action is "mortgage".
    g = game_factory(sheep_per_paddock=1, current="Jim")
    from tests.conftest import drain_cash
    session = SessionLocal()
    drain_cash(session, g.game_id, g.players["Jim"], 1900)
    session.close()
    return g


def drive(game_id, during_sleep=None, monkeypatch=None):
    async def fake_sleep(_delay):
        if during_sleep:
            with SessionLocal() as s:
                during_sleep(s)
                s.commit()
    monkeypatch.setattr(ai_autopilot.asyncio, "sleep", fake_sleep)
    asyncio.run(ai_autopilot._drive_one_game(game_id))


def turn_count(session, game_id):
    return session.query(models.Turn).filter_by(game_id=game_id).count()


def mortgaged_count(session, game_id):
    return session.query(models.Paddock).filter_by(
        game_id=game_id, is_mortgaged=True).count()


def test_autopilot_rolls_for_ai_when_nothing_changes(session, game, monkeypatch):
    drive(game.game_id, monkeypatch=monkeypatch)
    assert turn_count(session, game.game_id) == 1


def test_no_roll_when_turn_flips_to_human_mid_sleep(session, game, monkeypatch):
    """THE bug: play_turn() acts on whoever is current NOW."""
    def flip(s):
        s.query(models.Game).get(game.game_id).current_game_player_id = \
            game.players["Hu"]
    drive(game.game_id, during_sleep=flip, monkeypatch=monkeypatch)
    assert turn_count(session, game.game_id) == 0


def test_no_roll_when_pending_appears_mid_sleep(session, game, monkeypatch):
    def add_pending(s):
        t = models.Turn(game_id=game.game_id, turn_number=99,
                        active_game_player_id=game.players["Hu"],
                        dice_roll_1=1, dice_roll_2=1)
        s.add(t)
        s.flush()
        s.add(models.PendingAction(game_id=game.game_id, turn_id=t.turn_id,
                                   action_type="expense_payment",
                                   active_player_id=game.players["Hu"],
                                   action_data=json.dumps({})))
    drive(game.game_id, during_sleep=add_pending, monkeypatch=monkeypatch)
    assert turn_count(session, game.game_id) == 1  # only the injected one


def test_no_roll_when_game_completes_mid_sleep(session, game, monkeypatch):
    def complete(s):
        s.query(models.Game).get(game.game_id).status = "completed"
    drive(game.game_id, during_sleep=complete, monkeypatch=monkeypatch)
    assert turn_count(session, game.game_id) == 0


def test_mortgage_executes_when_still_valid(session, mortgage_game, monkeypatch):
    drive(mortgage_game.game_id, monkeypatch=monkeypatch)
    assert mortgaged_count(session, mortgage_game.game_id) == 1


def test_no_mortgage_when_turn_flips_mid_sleep(session, mortgage_game, monkeypatch):
    def flip(s):
        s.query(models.Game).get(mortgage_game.game_id).current_game_player_id = \
            mortgage_game.players["Hu"]
    drive(mortgage_game.game_id, during_sleep=flip, monkeypatch=monkeypatch)
    assert mortgaged_count(session, mortgage_game.game_id) == 0


def test_no_mortgage_when_cash_recovers_mid_sleep(session, mortgage_game, monkeypatch):
    """The decided candidate must still be the right move at execution."""
    def refund(s):
        s.add(models.Transaction(
            game_id=mortgage_game.game_id, player_from_id=None,
            player_to_id=mortgage_game.players["Jim"], amount=1900,
            transaction_type="test_refund"))
    drive(mortgage_game.game_id, during_sleep=refund, monkeypatch=monkeypatch)
    assert mortgaged_count(session, mortgage_game.game_id) == 0
