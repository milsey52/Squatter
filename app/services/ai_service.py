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
from app.constants import (
    MAX_PENS_PER_TRANSACTION,
    IMPROVED_PASTURE_COST,
    IRRIGATED_PASTURE_COST,
)


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

        # Haystack offers ride along on most Haymaking-season pendings
        # (data.haystack_available true) and also appear standalone as
        # action_type='haystack_offer'. Try to purchase before resolving
        # the main action.
        self._consider_haystack_purchase(data)

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

    # ── Station maintenance (between rolls) ────────────────────────────
    UPGRADE_CASH_BUFFER = 1500  # don't go broke

    def find_upgrade_candidate(self) -> dict | None:
        """If the AI should upgrade a paddock RIGHT NOW (it's their turn,
        no pending action), return {'paddock_number': N, 'target_type': T}.
        Returns None for Easy difficulty or when no affordable upgrade is
        available.
        Rule: upgrades only on own turn — caller must check that."""
        if self.difficulty == "easy":
            return None

        balance = self.ledger.player_balance(self.player.game_player_id)

        # Improved → Irrigated (only when all 5 are already improved/irrigated)
        irr_info = self.station.can_upgrade_to_irrigated(self.player.game_player_id)
        if irr_info["can_upgrade"] and balance >= IRRIGATED_PASTURE_COST + self.UPGRADE_CASH_BUFFER:
            paddocks = self.station.get_paddocks(self.player.game_player_id)
            improved = [p for p in paddocks if p.paddock_type == "improved" and not p.is_mortgaged]
            if improved:
                # Upgrade the first one (lowest paddock number).
                return {"paddock_number": improved[0].paddock_number, "target_type": "irrigated"}

        # Natural → Improved
        imp_info = self.station.can_upgrade_to_improved(self.player.game_player_id)
        if imp_info["can_upgrade"] and balance >= IMPROVED_PASTURE_COST + self.UPGRADE_CASH_BUFFER:
            paddock_no = imp_info["available_paddocks"][0]
            return {"paddock_number": paddock_no, "target_type": "improved"}

        return None

    def execute_upgrade(self, paddock_number: int, target_type: str) -> str:
        """Pay the cost and upgrade the paddock. Caller must ensure it's
        the AI's turn and that the upgrade is currently valid."""
        cost = IRRIGATED_PASTURE_COST if target_type == "irrigated" else IMPROVED_PASTURE_COST
        latest_turn = (
            self.session.query(models.Turn)
            .filter_by(game_id=self.game_id)
            .order_by(models.Turn.turn_id.desc())
            .first()
        )
        turn_id = latest_turn.turn_id if latest_turn else None
        self.ledger.pay_bank(
            self.player, cost, "paddock_upgrade", turn_id,
            notes=f"Upgraded paddock {paddock_number} to {target_type}",
        )
        self.station.upgrade_paddock(self.player.game_player_id, paddock_number, target_type)
        self.session.flush()
        return f"upgrade:{paddock_number}->{target_type}"

    # ── Helpers ────────────────────────────────────────────────────────
    def _consider_haystack_purchase(self, data: dict) -> bool:
        """If a haystack is on offer and the AI should buy it given its
        difficulty + cash, do so inline (deduct cash, set has_haystack).
        Returns True if bought."""
        if not data.get("haystack_available"):
            return False
        if self.player.has_haystack:
            return False
        cost = int(data.get("haystack_cost") or 0)
        if cost <= 0:
            return False
        balance = self.ledger.player_balance(self.player.game_player_id)
        if balance < cost:
            return False

        if self.difficulty == "easy":
            # Coin flip — Easy is random.
            if random.random() < 0.5:
                return False
        else:
            # Medium / Hard: buy when comfortably affordable. Always grab
            # one if in drought (already paying the drought premium means
            # we badly need offset capacity for future drought sales).
            buffer = 0 if self.player.is_in_drought else 1000
            if balance < cost + buffer:
                return False

        latest_turn = (
            self.session.query(models.Turn)
            .filter_by(game_id=self.game_id)
            .order_by(models.Turn.turn_id.desc())
            .first()
        )
        turn_id = latest_turn.turn_id if latest_turn else None
        notes = "Bought haystack" + (" (drought premium)" if self.player.is_in_drought else "")
        self.ledger.pay_bank(self.player, cost, "haystack_purchase", turn_id, notes=notes)
        self.player.has_haystack = True
        self.session.flush()
        return True

    def _has_high_stock_prices_card(self) -> bool:
        return (
            self.session.query(models.CardDraw)
            .join(models.Card, models.CardDraw.card_id == models.Card.card_id)
            .filter(
                models.CardDraw.game_id == self.game_id,
                models.CardDraw.kept_by_player_id == self.player.game_player_id,
                models.CardDraw.discarded_at.is_(None),
                models.Card.effect_code == "HIGH_STOCK_PRICES",
            )
            .first()
        ) is not None

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
        if self.difficulty in ("medium", "hard"):
            return self._stock_sale_decision_medium(data)
        return self._stock_sale_decision_easy(data)

    def _stock_sale_decision_easy(self, data: dict) -> str:
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
        if self.difficulty in ("medium", "hard"):
            return self._stud_ram_purchase_medium(data)
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
        if self.difficulty in ("medium", "hard"):
            return self._expense_payment_medium(data)
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

    # ── Medium heuristics ──────────────────────────────────────────────
    # Use only the public action_data + own holdings — no peeking at the
    # next Tucker Bag / Stock Sale card.

    def _stock_sale_decision_medium(self, data: dict) -> str:
        in_drought = bool(data.get("in_drought"))
        restock_blocked = bool(data.get("restock_blocked"))
        block_scope = data.get("restock_block_scope")
        empty_pens = int(data.get("empty_pens", 0) or 0)
        empty_irrigated = int(data.get("empty_irrigated_pens", 0) or 0)
        total_pens = int(data.get("total_pens", 0) or 0)
        natural_pens = int(data.get("natural_pens", 0) or 0)
        improved_pens = int(data.get("improved_pens", 0) or 0)
        irrigated_pens = int(data.get("irrigated_pens", 0) or 0)
        max_per_txn = int(data.get("max_per_transaction", MAX_PENS_PER_TRANSACTION) or MAX_PENS_PER_TRANSACTION)
        balance = self.ledger.player_balance(self.player.game_player_id)
        has_hsp = self._has_high_stock_prices_card()

        # Capacity to buy under current restrictions
        if restock_blocked and block_scope == "all":
            buy_capacity = 0
        elif in_drought:
            buy_capacity = empty_irrigated
        elif restock_blocked and block_scope == "irrigated":
            buy_capacity = max(0, empty_pens - empty_irrigated)
        else:
            buy_capacity = empty_pens
        buy_capacity = min(buy_capacity, max_per_txn)

        # In drought: be defensive — half-price sells hurt; just pass.
        if in_drought:
            self.decision.stock_sale_pass(self.player.game_player_id)
            return "stock_sale:passed_drought"

        # Sell heuristic — skim profits when sheep are plentiful, especially
        # if we have an HSP card to amplify the gain.
        SELL_THRESHOLD_NORMAL = 12
        SELL_THRESHOLD_HSP = 8
        sell_threshold = SELL_THRESHOLD_HSP if has_hsp else SELL_THRESHOLD_NORMAL
        if total_pens >= sell_threshold and total_pens >= 1:
            target = min(5, total_pens, max_per_txn)
            # Sell preference: Improved → Natural → Irrigated.
            # Improved tier earns the higher Stock Sale price; Natural earns
            # the lower price but is also drought-vulnerable; Irrigated is
            # drought-immune so keep it.
            remaining = target
            sell_i = min(remaining, improved_pens); remaining -= sell_i
            sell_n = min(remaining, natural_pens); remaining -= sell_n
            sell_r = min(remaining, irrigated_pens); remaining -= sell_r
            total_sell = sell_i + sell_n + sell_r
            if total_sell == 0:
                self.decision.stock_sale_pass(self.player.game_player_id)
                return "stock_sale:sell_zero_passed"
            try:
                self.decision.stock_sale_sell(
                    self.player.game_player_id,
                    pens=total_sell,
                    use_high_stock_prices=has_hsp,
                    use_auto_sell_modifier=True,
                    pens_by_type={"natural": sell_n, "improved": sell_i, "irrigated": sell_r},
                )
            except ValueError:
                self.decision.stock_sale_pass(self.player.game_player_id)
                return "stock_sale:sell_failed_passed"
            tag = "_hsp" if has_hsp else ""
            return f"stock_sale:sold_{total_sell}{tag}"

        # Buy heuristic — restock when capacity & cash allow.
        BUY_THRESHOLD_PENS = 5
        BUY_FLOOR_CASH = 3000
        if (buy_capacity >= 1 and total_pens < BUY_THRESHOLD_PENS
                and balance >= BUY_FLOOR_CASH):
            qty = min(5, buy_capacity)
            try:
                self.decision.stock_sale_buy(
                    self.player.game_player_id, qty,
                    use_high_stock_prices=False,
                )
                return f"stock_sale:bought_{qty}"
            except ValueError:
                pass

        self.decision.stock_sale_pass(self.player.game_player_id)
        return "stock_sale:passed"

    def _stud_ram_purchase_medium(self, data: dict) -> str:
        price = int(data.get("purchase_price", 0) or 0)
        balance = self.ledger.player_balance(self.player.game_player_id)
        total_pens = self.station.get_total_pens(self.player.game_player_id)
        in_drought = bool(self.player.is_in_drought)
        # Buy if comfortably affordable, not in drought, and we have enough
        # sheep for the wool bonus to pay back.
        if (balance >= price + 1500
                and not in_drought
                and total_pens >= 4):
            try:
                self.decision.stud_ram_buy(self.player.game_player_id)
                return "stud_ram:bought"
            except ValueError:
                pass
        self.decision.stud_ram_pass(self.player.game_player_id)
        return "stud_ram:passed"

    def _expense_payment_medium(self, data: dict) -> str:
        if data.get("alternative_payment"):
            # Drench Sheep for Worms: enhanced grants +20% next sell bonus
            # and the Worm Control card. Worth it when we have stock and cash.
            total_pens = int(data.get("total_pens", 0) or 0)
            balance = self.ledger.player_balance(self.player.game_player_id)
            enhanced_cost = data.get("enhanced_option", {}).get("cost", 0) or 0
            choose_enhanced = (
                total_pens >= 5 and balance >= enhanced_cost + 1000
            )
            option = "enhanced" if choose_enhanced else "basic"
            try:
                self.decision.expense_acknowledge(self.player.game_player_id, option=option)
                return f"expense:{option}"
            except ValueError:
                try:
                    self.decision.expense_acknowledge(self.player.game_player_id, option="basic")
                    return "expense:basic_fallback"
                except ValueError:
                    pass
            return "expense:no_op"
        # Regular expense: decline the optional immunity card; just OK.
        try:
            self.decision.expense_acknowledge(self.player.game_player_id, buy_card=False)
        except ValueError:
            pass
        return "expense:ok"
