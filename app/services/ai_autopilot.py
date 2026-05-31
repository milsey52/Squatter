"""Server-side autopilot that drives AI players.

A single async task scans every active game on a short interval. For each
game it:
  - During turn-order rolling, rolls dice for any AI that hasn't rolled
    this round yet.
  - During in-progress play, resolves any pending action belonging to an
    AI (Tucker Bag acknowledge, Stock Sale decision, etc.).
  - Otherwise, if the current player is an AI with no pending action,
    starts their turn (rolls dice via TurnManager).

The autopilot calls service methods directly (not HTTP routes) and
broadcasts events so connected human clients refresh.
"""
import asyncio
import json
import random
import traceback

from sqlalchemy.orm import Session

from app import models
from app.db import SessionLocal
from app.services.ai_service import AIPlayerService
from app.services.decision_service import DecisionService
from app.services.turn_manager import TurnManager
from app.api.routes import events


POLL_INTERVAL_SECONDS = 3.0
ERROR_BACKOFF_SECONDS = 5.0


async def run_autopilot():
    """Top-level loop. Spawned from main.py startup."""
    while True:
        try:
            await _tick()
        except Exception:  # never let the loop die
            traceback.print_exc()
            await asyncio.sleep(ERROR_BACKOFF_SECONDS)
            continue
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def _tick():
    """One pass over all active games."""
    with SessionLocal() as session:
        games = (
            session.query(models.Game)
            .filter(models.Game.status.in_(["in_progress", "rolling_for_order"]))
            .all()
        )
        # Snapshot ids so we don't hold the same session across each game.
        game_ids = [g.game_id for g in games]

    for gid in game_ids:
        try:
            await _drive_one_game(gid)
        except Exception:
            traceback.print_exc()


async def _drive_one_game(game_id: int):
    """Make at most one move in this game (if an AI is up to act)."""
    with SessionLocal() as session:
        game = session.query(models.Game).filter_by(game_id=game_id).first()
        if not game:
            return

        if game.status == "rolling_for_order":
            event = _maybe_roll_for_turn_order(session, game)
            session.commit()
            if event:
                await events.broadcast_game_event(game_id, event[0], event[1])
            return

        if game.status != "in_progress":
            return

        # First priority: any pending action belonging to an AI player.
        pending_for_ai = _find_pending_for_ai(session, game)
        if pending_for_ai is not None:
            ai_player, pending = pending_for_ai
            try:
                service = AIPlayerService(session, game_id, ai_player)
                service.handle_pending(pending)
                session.commit()
            except Exception:
                session.rollback()
                traceback.print_exc()
                return
            await events.broadcast_game_event(
                game_id, "game_state_changed",
                {"reason": "ai_acted", "action_type": pending.action_type,
                 "player_id": ai_player.game_player_id}
            )
            return

        # Second: if the current player is an AI and there's no pending
        # for ANY player, roll dice. Mirrors the human /turns route guard:
        # an unresolved pending (e.g., the previous player's Tucker Bag
        # popup) blocks the next dice roll.
        any_unresolved = (
            session.query(models.PendingAction)
            .filter(
                models.PendingAction.game_id == game_id,
                models.PendingAction.resolved_at.is_(None),
            )
            .first()
        )
        if any_unresolved is not None:
            return
        current = session.query(models.GamePlayer).filter_by(
            game_player_id=game.current_game_player_id
        ).first()
        if not current or not current.is_ai or not current.is_active:
            return
        # Skip if the AI is in Visiting Town (TurnManager handles skip count).
        try:
            tm = TurnManager(session, game_id)
            tm.play_turn()
            session.commit()
        except Exception:
            session.rollback()
            traceback.print_exc()
            return

        # Broadcast turn_played
        turn = (
            session.query(models.Turn)
            .filter(models.Turn.game_id == game_id)
            .order_by(models.Turn.turn_number.desc())
            .first()
        )
        decision_service = DecisionService(session, game_id)
        pending_state = decision_service.get_pending_action_state()
        updated = session.query(models.GamePlayer).filter_by(
            game_player_id=turn.active_game_player_id
        ).first()
        await events.broadcast_game_event(
            game_id, "turn_played",
            {
                "turn_number": turn.turn_number,
                "player_id": turn.active_game_player_id,
                "dice_roll": [turn.dice_roll_1, turn.dice_roll_2],
                "is_double": turn.is_double,
                "new_position": updated.current_space_id if updated else None,
                "visiting_town_turns": updated.visiting_town_turns if updated else 0,
                "is_in_drought": updated.is_in_drought if updated else False,
                "has_pending_action": pending_state is not None,
                "pending_action": pending_state,
            }
        )


def _find_pending_for_ai(session: Session, game) -> tuple | None:
    """Return (ai_player, pending) for the oldest unresolved pending whose
    active_player_id is an AI, or None."""
    pendings = (
        session.query(models.PendingAction)
        .filter(
            models.PendingAction.game_id == game.game_id,
            models.PendingAction.resolved_at.is_(None),
        )
        .order_by(models.PendingAction.pending_action_id.asc())
        .all()
    )
    for p in pendings:
        if p.active_player_id is None:
            # Auctions / multi-actor. Check if any AI is eligible to decline.
            if p.action_type == "fire_fighting_auction" and p.action_data:
                data = json.loads(p.action_data)
                eligible_ids = [e["id"] for e in data.get("eligible_players", [])]
                declined = set(data.get("declined", []))
                current_bidder = data.get("current_bidder_id")
                for eid in eligible_ids:
                    if eid in declined or eid == current_bidder:
                        continue
                    ai = session.query(models.GamePlayer).filter_by(
                        game_player_id=eid, is_ai=True
                    ).first()
                    if ai:
                        return (ai, p)
            continue
        ai = session.query(models.GamePlayer).filter_by(
            game_player_id=p.active_player_id, is_ai=True
        ).first()
        if ai:
            return (ai, p)
    return None


def _maybe_roll_for_turn_order(session: Session, game) -> tuple | None:
    """During rolling_for_order, roll dice for the first AI that hasn't
    rolled in the current round. Returns (event_name, payload) to broadcast
    or None if nothing to do."""
    current_round = game.current_turn_order_round or 1
    ais = (
        session.query(models.GamePlayer)
        .filter_by(game_id=game.game_id, is_ai=True, is_active=True)
        .all()
    )
    for ai in ais:
        existing = (
            session.query(models.TurnOrderRoll)
            .filter_by(
                game_id=game.game_id,
                game_player_id=ai.game_player_id,
                round_number=current_round,
            )
            .first()
        )
        if existing:
            continue
        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)
        roll = models.TurnOrderRoll(
            game_id=game.game_id,
            game_player_id=ai.game_player_id,
            round_number=current_round,
            dice_roll_1=d1,
            dice_roll_2=d2,
            total=d1 + d2,
        )
        session.add(roll)
        return ("turn_order_roll", {
            "player_id": ai.game_player_id,
            "player_name": ai.player_name,
            "dice1": d1, "dice2": d2, "total": d1 + d2,
            "round": current_round,
        })
    return None
