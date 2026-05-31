"""AI player decision logic.

For v1 we only implement EASY = random valid moves. MEDIUM/HARD will
override individual decision methods later.

All policies use only public-API-readable state for the AI player itself
plus public opponent state — never peek at hidden cards or upcoming
draws.
"""
import json
import random
from sqlalchemy.orm import Session

from app import models
from app.services.decision_service import DecisionService
from app.services.station_service import StationService
from app.services.ledger_service import LedgerService
from app.constants import MAX_PENS_PER_TRANSACTION


class AIPlayerService:
    def __init__(self, session: Session, game_id: int, player: models.GamePlayer):
        self.session = session
        self.game_id = game_id
        self.player = player
        self.decision = DecisionService(session, game_id)
        self.station = StationService(session, game_id)
        self.ledger = LedgerService(session, game_id)
        self.difficulty = (player.ai_difficulty or "easy").lower()

    # ── Pending-action dispatch ────────────────────────────────────────
    def handle_pending(self, pending: models.PendingAction) -> str:
        """Resolve one pending action belonging to this AI. Returns a short
        tag describing what was done (for logging / event broadcast)."""
        data = json.loads(pending.action_data) if pending.action_data else {}
        action_type = pending.action_type

        if action_type == "tucker_bag_drawn":
            return self._tucker_bag_drawn(data)
        if action_type == "stock_sale_decision":
            return self._stock_sale_decision(data)
        if action_type == "stud_ram_purchase":
            return self._stud_ram_purchase(data)
        if action_type == "expense_payment":
            return self._expense_payment(data)
        if action_type == "fire_fighting_offer":
            # AI declines FFE offers in v1
            self.decision.fire_fighting_offer_respond(self.player.game_player_id, accept=False)
            return "fire_fighting_offer:declined"
        if action_type == "fire_fighting_auction":
            # AI always declines auctions in v1
            try:
                self.decision.fire_fighting_auction_decline(self.player.game_player_id)
            except ValueError:
                pass
            return "fire_fighting_auction:declined"

        # Everything else is purely informational — acknowledge.
        try:
            self.decision.acknowledge(self.player.game_player_id)
        except ValueError:
            pass
        return f"{action_type}:acknowledged"

    # ── Decisions ──────────────────────────────────────────────────────
    def _tucker_bag_drawn(self, data: dict) -> str:
        # Free retainables keep automatically (server-side). Purchasable
        # retainables (FFE @ $350): AI declines in v1. Non-retainables: OK.
        is_retainable = bool(data.get("is_retainable"))
        purchase_price = data.get("purchase_price", 0) or 0
        if is_retainable and purchase_price > 0:
            buy_card = False  # decline FFE in v1
        else:
            buy_card = bool(is_retainable)
        self.decision.tucker_bag_acknowledge(self.player.game_player_id, buy_card=buy_card)
        return "tucker_bag:acknowledged"

    def _stock_sale_decision(self, data: dict) -> str:
        in_drought = bool(data.get("in_drought"))
        empty_pens = int(data.get("empty_pens", 0) or 0)
        total_pens = int(data.get("total_pens", 0) or 0)
        empty_irrigated = int(data.get("empty_irrigated_pens", 0) or 0)
        natural_pens = int(data.get("natural_pens", 0) or 0)
        improved_pens = int(data.get("improved_pens", 0) or 0)
        irrigated_pens = int(data.get("irrigated_pens", 0) or 0)
        restock_blocked = bool(data.get("restock_blocked"))
        block_scope = data.get("restock_block_scope")
        max_per_txn = data.get("max_per_transaction", MAX_PENS_PER_TRANSACTION) or MAX_PENS_PER_TRANSACTION

        # Compute valid buy capacity under drought + block scopes
        if restock_blocked and block_scope == "all":
            buy_capacity = 0
        elif in_drought:
            buy_capacity = empty_irrigated
        elif restock_blocked and block_scope == "irrigated":
            buy_capacity = max(0, empty_pens - empty_irrigated)
        else:
            buy_capacity = empty_pens
        buy_capacity = min(buy_capacity, max_per_txn)

        sell_capacity = min(total_pens, max_per_txn)

        choices = []
        if buy_capacity >= 1:
            choices.append("buy")
        if sell_capacity >= 1:
            choices.append("sell")
        choices.append("pass")

        # Easy: random of valid actions
        action = random.choice(choices)

        if action == "pass":
            self.decision.stock_sale_pass(self.player.game_player_id)
            return "stock_sale:passed"

        if action == "buy":
            pens = random.randint(1, min(buy_capacity, 5))
            try:
                self.decision.stock_sale_buy(self.player.game_player_id, pens,
                                             use_high_stock_prices=False)
            except ValueError:
                # If unaffordable, pass instead.
                self.decision.stock_sale_pass(self.player.game_player_id)
                return "stock_sale:buy_failed_passed"
            return f"stock_sale:bought_{pens}"

        # action == "sell"
        target = random.randint(1, min(sell_capacity, 5))
        # Distribute across tiers randomly, respecting held caps
        remaining = target
        sell_n = min(remaining, natural_pens)
        sell_n = random.randint(0, sell_n) if sell_n > 0 else 0
        remaining -= sell_n
        sell_i = min(remaining, improved_pens)
        sell_i = random.randint(0, sell_i) if sell_i > 0 else 0
        remaining -= sell_i
        sell_r = min(remaining, irrigated_pens)
        # Fill remainder greedily so total = target if possible
        if remaining > 0 and sell_r < remaining:
            shortfall = remaining - sell_r
            # Try to top up from other tiers first
            top_n = min(shortfall, natural_pens - sell_n)
            sell_n += top_n
            shortfall -= top_n
            if shortfall > 0:
                top_i = min(shortfall, improved_pens - sell_i)
                sell_i += top_i
                shortfall -= top_i
            sell_r = min(sell_r, irrigated_pens)
        else:
            sell_r = remaining

        # Safety clamp
        sell_n = max(0, min(sell_n, natural_pens))
        sell_i = max(0, min(sell_i, improved_pens))
        sell_r = max(0, min(sell_r, irrigated_pens))
        total_sell = sell_n + sell_i + sell_r
        if total_sell == 0:
            self.decision.stock_sale_pass(self.player.game_player_id)
            return "stock_sale:sell_zero_passed"

        try:
            self.decision.stock_sale_sell(
                self.player.game_player_id,
                pens=total_sell,
                use_high_stock_prices=False,
                use_auto_sell_modifier=True,
                pens_by_type={"natural": sell_n, "improved": sell_i, "irrigated": sell_r},
            )
        except ValueError:
            self.decision.stock_sale_pass(self.player.game_player_id)
            return "stock_sale:sell_failed_passed"
        return f"stock_sale:sold_{total_sell}"

    def _stud_ram_purchase(self, data: dict) -> str:
        # Easy: 50/50 buy/pass if affordable
        price = int(data.get("purchase_price", 0) or 0)
        balance = self.ledger.player_balance(self.player.game_player_id)
        if balance >= price and random.random() < 0.5:
            try:
                self.decision.stud_ram_buy(self.player.game_player_id)
                return "stud_ram:bought"
            except ValueError:
                pass
        self.decision.stud_ram_pass(self.player.game_player_id)
        return "stud_ram:passed"

    def _expense_payment(self, data: dict) -> str:
        # Drench (alternative_payment): 50/50 basic/enhanced
        if data.get("alternative_payment"):
            option = random.choice(["basic", "enhanced"])
            try:
                self.decision.expense_acknowledge(self.player.game_player_id, option=option)
                return f"expense:{option}"
            except ValueError:
                # Insufficient funds on enhanced — fall back to basic
                try:
                    self.decision.expense_acknowledge(self.player.game_player_id, option="basic")
                    return "expense:basic_fallback"
                except ValueError:
                    pass
        # Regular expense: optional immunity card — Easy declines, just OK.
        try:
            self.decision.expense_acknowledge(self.player.game_player_id, buy_card=False)
        except ValueError:
            pass
        return "expense:ok"
