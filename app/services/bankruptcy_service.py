# app/services/bankruptcy_service.py
"""Debt and elimination rules.

A player whose balance goes negative (forced expenses, mortgage interest,
card effects) must raise cash before rolling again — emergency sheep sales,
mortgages, stud ram / haystack sales. If even FULL liquidation cannot clear
the debt, the player is bankrupt and retires from the game (Squatter manual:
a player who cannot meet commitments is out). Last active player standing
wins.
"""
import json

from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app import models
from app.constants import (
    EMERGENCY_SELL_PRICE_PER_PEN,
    STUD_RAM_SELL_PRICE,
    HAYSTACK_SELL_PRICE,
    MORTGAGE_NATURAL,
    MORTGAGE_IMPROVED,
    MORTGAGE_IRRIGATED,
)
from app.services.ledger_service import LedgerService
from app.services.station_service import StationService

MORTGAGE_VALUES = {
    "natural": MORTGAGE_NATURAL,
    "improved": MORTGAGE_IMPROVED,
    "irrigated": MORTGAGE_IRRIGATED,
}


class InDebtError(Exception):
    """The player owes money but CAN recover by liquidating assets.
    The roll is refused until the debt is cleared."""

    def __init__(self, balance: int):
        self.balance = balance
        super().__init__(
            f"In debt ${-balance} — sell sheep to the bank or mortgage "
            "paddocks before rolling"
        )


class BankruptcyService:
    def __init__(self, session: Session, game_id: int):
        self.session = session
        self.game_id = game_id
        self.ledger = LedgerService(session, game_id)
        self.station = StationService(session, game_id)

    def liquidation_value(self, player_id: int) -> int:
        """Everything the player could raise: emergency sheep sales,
        mortgaging every unmortgaged paddock (selling sheep first lifts the
        8-pen mortgage restriction), stud rams and haystack sold back."""
        player = self.session.query(models.GamePlayer).get(player_id)
        pens = self.station.get_total_pens(player_id)
        value = pens * EMERGENCY_SELL_PRICE_PER_PEN
        for paddock in self.station.get_paddocks(player_id):
            if not paddock.is_mortgaged:
                value += MORTGAGE_VALUES[paddock.paddock_type]
        value += len(self.station.get_stud_rams_owned(player_id)) * STUD_RAM_SELL_PRICE
        if player and player.has_haystack:
            value += HAYSTACK_SELL_PRICE
        return value

    def can_recover(self, player_id: int) -> bool:
        """True when full liquidation would clear the debt."""
        balance = self.ledger.player_balance(player_id)
        return balance + self.liquidation_value(player_id) >= 0

    # ── Debt-settlement gate ────────────────────────────────────────────
    # When a forced payment leaves a player in the red, the game must halt
    # (pending actions block every player's roll) until the debtor raises
    # the cash — or, if their assets can't cover it, they go bankrupt on
    # the spot so the game is never deadlocked waiting on them.

    def find_open_debt_pending(self, player_id: int):
        return (
            self.session.query(models.PendingAction)
            .filter_by(
                game_id=self.game_id,
                action_type="debt_settlement",
                active_player_id=player_id,
                resolved_at=None,
            )
            .first()
        )

    def check_debt(self, player: models.GamePlayer, turn_id):
        """Call after anything that can charge a player. Returns
        'debt_pending', 'bankrupt', or None when solvent."""
        balance = self.ledger.player_balance(player.game_player_id)
        if balance >= 0:
            return None
        if not self.can_recover(player.game_player_id):
            next_player = self._next_active_after(player)
            self.eliminate(player, turn_id)
            if not self.declare_last_standing_winner(turn_id):
                game = self.session.query(models.Game).get(self.game_id)
                if (game.current_game_player_id == player.game_player_id
                        and next_player is not None):
                    game.current_game_player_id = next_player.game_player_id
            self.session.flush()
            return "bankrupt"
        if self.find_open_debt_pending(player.game_player_id) is None:
            self.session.add(models.PendingAction(
                game_id=self.game_id,
                turn_id=turn_id,
                action_type="debt_settlement",
                active_player_id=player.game_player_id,
                action_data=json.dumps({
                    "player_id": player.game_player_id,
                    "player_name": player.player_name,
                    "debt": -balance,
                }),
            ))
            self.session.flush()
        return "debt_pending"

    def clear_debt_pending_if_solvent(self, player_id: int) -> bool:
        """Resolve the debt gate once the debtor is back at >= $0.
        Called after every cash-raising action (asset sales, mortgages,
        trades). Returns True if a pending was resolved."""
        pending = self.find_open_debt_pending(player_id)
        if pending is None:
            return False
        if self.ledger.player_balance(player_id) < 0:
            return False
        pending.resolved_at = func.now()
        self.session.flush()
        return True

    def _next_active_after(self, player: models.GamePlayer):
        players = (
            self.session.query(models.GamePlayer)
            .filter_by(game_id=self.game_id, is_active=True)
            .order_by(models.GamePlayer.turn_order)
            .all()
        )
        others = [p for p in players
                  if p.game_player_id != player.game_player_id]
        if not others:
            return None
        later = [p for p in others if p.turn_order > player.turn_order]
        return later[0] if later else others[0]

    def eliminate(self, player: models.GamePlayer, turn_id) -> None:
        """Retire the player: out of the rotation, and any pending actions
        waiting on them are resolved so they can never block the game."""
        player.is_active = False
        open_pendings = (
            self.session.query(models.PendingAction)
            .filter(
                models.PendingAction.game_id == self.game_id,
                models.PendingAction.active_player_id == player.game_player_id,
                models.PendingAction.resolved_at.is_(None),
            )
            .all()
        )
        for pending in open_pendings:
            pending.resolved_at = func.now()
        self.session.flush()

    def declare_last_standing_winner(self, turn_id) -> bool:
        """If exactly one active player remains, they win. Mirrors the
        guard pattern of StationService.declare_winner_if_eligible."""
        survivors = (
            self.session.query(models.GamePlayer)
            .filter_by(game_id=self.game_id, is_active=True)
            .all()
        )
        if len(survivors) != 1:
            return False
        game = self.session.query(models.Game).get(self.game_id)
        if game.status == "completed":
            return False
        existing = (
            self.session.query(models.PendingAction)
            .filter_by(game_id=self.game_id, action_type="game_won")
            .first()
        )
        if existing:
            return False
        winner = survivors[0]
        game.status = "completed"
        self.session.add(models.PendingAction(
            game_id=self.game_id,
            turn_id=turn_id,
            action_type="game_won",
            active_player_id=winner.game_player_id,
            action_data=json.dumps({
                "winner_id": winner.game_player_id,
                "winner_name": winner.player_name,
                "reason": "last_player_standing",
            }),
        ))
        self.session.flush()
        return True
