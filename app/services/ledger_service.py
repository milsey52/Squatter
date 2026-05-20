# app/services/ledger_service.py
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app import models

BANK_PLAYER_ID = None  # None represents the bank in transactions


class LedgerService:
    def __init__(self, session: Session, game_id: int):
        self.session = session
        self.game_id = game_id

    # ── Public helpers ──────────────────────────────────────────────────

    def transfer(
        self,
        payer: models.GamePlayer,
        payee_id: Optional[int],
        amount: int,
        txn_type: str,
        turn_id: Optional[int],
        space_id: Optional[int] = None,
        card_id: Optional[int] = None,
        notes: Optional[str] = None,
    ):
        """Money moves from payer to payee (payee_id None -> bank)."""
        if amount <= 0:
            raise ValueError("Amount must be positive")

        txn = models.Transaction(
            game_id=self.game_id,
            turn_id=turn_id,
            sequence_in_turn=self._next_sequence(turn_id),
            player_from_id=payer.game_player_id,
            player_to_id=payee_id,
            amount=amount,
            transaction_type=txn_type,
            space_id=space_id,
            card_id=card_id,
            notes=notes,
        )
        self.session.add(txn)
        self.session.flush()
        return txn

    def pay_bank(self, player, amount, txn_type, turn_id, **kwargs):
        return self.transfer(player, BANK_PLAYER_ID, amount, txn_type, turn_id, **kwargs)

    def pay_player(self, from_player, to_player, amount, txn_type, turn_id, **kwargs):
        return self.transfer(from_player, to_player.game_player_id, amount, txn_type, turn_id, **kwargs)

    def receive_from_bank(self, player, amount, txn_type, turn_id, **kwargs):
        return self.transfer(
            payer=models.GamePlayer(game_player_id=None),
            payee_id=player.game_player_id,
            amount=amount,
            txn_type=txn_type,
            turn_id=turn_id,
            **kwargs,
        )

    def record_wool_cheque(self, player, amount, turn_id=None, notes="Wool Cheque"):
        return self.receive_from_bank(
            player, amount, "wool_cheque", turn_id,
            notes=notes,
        )

    def record_mortgage_interest(self, player, amount, turn_id=None):
        if amount > 0:
            return self.pay_bank(
                player, amount, "mortgage_interest", turn_id,
                notes="Mortgage interest payment",
            )

    def record_bank_payment(self, player, amount, txn_type, turn_id=None):
        return self.pay_bank(player, amount, txn_type, turn_id)

    def record_bank_reward(self, player, amount, txn_type, turn_id=None, **kwargs):
        return self.receive_from_bank(player, amount, txn_type, turn_id, **kwargs)

    def player_balance(self, player_id: int) -> int:
        incoming = (
            self.session.query(func.coalesce(func.sum(models.Transaction.amount), 0))
            .filter(
                models.Transaction.game_id == self.game_id,
                models.Transaction.player_to_id == player_id,
            )
            .scalar()
        )
        outgoing = (
            self.session.query(func.coalesce(func.sum(models.Transaction.amount), 0))
            .filter(
                models.Transaction.game_id == self.game_id,
                models.Transaction.player_from_id == player_id,
            )
            .scalar()
        )
        starting_cash = self._game_rules().starting_cash
        return starting_cash + incoming - outgoing

    def get_balance(self, player_id: int) -> int:
        return self.player_balance(player_id)

    # ── Internal helpers ────────────────────────────────────────────────

    def _next_sequence(self, turn_id):
        if turn_id is None:
            return None
        seq = (
            self.session.query(func.max(models.Transaction.sequence_in_turn))
            .filter(models.Transaction.turn_id == turn_id)
            .scalar()
        )
        return (seq or 0) + 1

    def _game_rules(self):
        rules = (
            self.session.query(models.GameRule)
            .filter(models.GameRule.game_id == self.game_id)
            .first()
        )
        if rules is None:
            raise ValueError(f"No game rules found for game_id={self.game_id}")
        return rules
