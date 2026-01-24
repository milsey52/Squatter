# app/services/jackpot_service.py
from sqlalchemy.orm import Session
from sqlalchemy import func
from app import models

class JackpotService:
    def __init__(self, session: Session, game_id: int):
        self.session = session
        self.game_id = game_id
        self._rules = self._house_rules()

    @property
    def enabled(self) -> bool:
        return bool(self._rules.jackpot_enabled)

    def contribute(self, amount: int, turn_id=None, transaction_id=None):
        if not self.enabled or amount <= 0:
            return
        balance = self.current_balance() + amount
        entry = models.JackpotLedger(
            game_id=self.game_id,
            turn_id=turn_id,
            transaction_id=transaction_id,
            delta_amount=amount,
            balance_after=balance,
        )
        self.session.add(entry)

    def payout(self, turn_id, player):
        if not self.enabled:
            return 0
        balance = self.current_balance()
        if balance <= 0:
            return 0
        entry = models.JackpotLedger(
            game_id=self.game_id,
            turn_id=turn_id,
            transaction_id=None,
            delta_amount=-balance,
            balance_after=0,
        )
        self.session.add(entry)
        return balance

    def current_balance(self) -> int:
        total = (
            self.session.query(func.coalesce(func.sum(models.JackpotLedger.delta_amount), 0))
            .filter(models.JackpotLedger.game_id == self.game_id)
            .scalar()
        )
        return total or 0

    def _house_rules(self):
        rules = (
            self.session.query(models.HouseRule)
            .filter(models.HouseRule.game_id == self.game_id)
            .first()
        )
        if rules is None:
            raise ValueError(f"No house rules found for game_id={self.game_id}")
        return rules