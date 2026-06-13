"""AI player decision logic.

For v1 we only implement EASY = random valid moves. MEDIUM/HARD will
override individual decision methods later.

All policies use only public-API-readable state for the AI player itself
plus public opponent state — never peek at hidden cards or upcoming
draws.
"""
import json
import random
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.services.decision_service import DecisionService
from app.services.station_service import StationService
from app.services.ledger_service import LedgerService
from app.constants import (
    MAX_PENS_PER_TRANSACTION,
    IMPROVED_PASTURE_COST,
    IRRIGATED_PASTURE_COST,
    MORTGAGE_NATURAL,
    MORTGAGE_IMPROVED,
    MORTGAGE_IRRIGATED,
    MORTGAGE_INTEREST_RATE,
    EMERGENCY_SELL_PRICE_PER_PEN,
    STUD_RAM_SELL_PRICE,
    HAYSTACK_SELL_PRICE,
)


# Difficulty-keyed heuristic thresholds. Hard is more aggressive across
# the board: sells sooner, buys with less cushion, upgrades with a
# smaller buffer, defers mortgages, and unmortgages sooner.
THRESHOLDS = {
    "medium": {
        # Win condition is 30 pens on all-irrigated. Sell only when very
        # close to max; otherwise keep buying toward the win.
        "sell_threshold_pens": 25,
        "sell_threshold_pens_hsp": 18,
        "buy_threshold_pens": 28,
        "buy_qty": 8,  # buy this many pens per stock sale when affordable
        "buy_floor_cash": 2000,
        # Cash to still hold AFTER buying stock — cushion for expense
        # spaces, drought, and mortgage interest ahead.
        "buy_cash_reserve": 500,
        "stud_ram_cash_buffer": 1500,
        "stud_ram_min_pens": 4,
        "drench_enhanced_min_pens": 5,
        "drench_enhanced_cash_buffer": 1000,
        "upgrade_cash_buffer": 1500,
        "mortgage_cash_floor": 200,    # mortgage if cash drops below this
        "lift_mortgage_cash_floor": 2500,  # lift if cash above this
        "haystack_cash_buffer": 1000,
    },
    "hard": {
        "sell_threshold_pens": 28,
        # HSP timing: Hard *saves* the card for a bigger sell rather than
        # burning it at low pen count. With HSP, hold off until pens >= 25.
        "sell_threshold_pens_hsp": 25,
        "buy_threshold_pens": 30,  # buy until full
        "buy_qty": 10,
        "buy_floor_cash": 1500,
        "buy_cash_reserve": 250,  # Hard runs leaner
        "stud_ram_cash_buffer": 1000,
        "stud_ram_min_pens": 3,
        "drench_enhanced_min_pens": 4,
        "drench_enhanced_cash_buffer": 800,
        "upgrade_cash_buffer": 800,
        "mortgage_cash_floor": 100,
        "lift_mortgage_cash_floor": 1500,
        "haystack_cash_buffer": 500,
        # FFE auction
        "ffe_max_bid": 600,
        "ffe_bid_increment": 50,
        "ffe_cash_buffer": 500,
        # Drought-imminent: when a Local Drought space is within
        # this many spaces ahead, add the extra cash reserve to every
        # cash-out decision.
        "drought_lookahead_spaces": 10,
        "drought_extra_buffer": 500,
    },
}

# Local Drought spaces on the current board (board_index, 0-based).
LOCAL_DROUGHT_BOARD_INDICES = {22, 43}
BOARD_SIZE = 44


class AIPlayerService:
    def __init__(self, session: Session, game_id: int, player: models.GamePlayer):
        self.session = session
        self.game_id = game_id
        self.player = player
        self.decision = DecisionService(session, game_id)
        self.station = StationService(session, game_id)
        self.ledger = LedgerService(session, game_id)
        self.difficulty = (player.ai_difficulty or "easy").lower()
        # Hard inherits Medium's threshold dict for any keys it doesn't override.
        self.t = THRESHOLDS.get(self.difficulty, THRESHOLDS["medium"])

    # ── "Thinking out loud" narration ──────────────────────────────────
    # Truthful, rule-derived summaries of what the AI is about to do and why,
    # shown during the autopilot's display-delay pause. These read the same
    # state/thresholds the decisions use; they never mutate anything.
    def _name(self) -> str:
        return self.player.player_name

    def thinking_summary(self, action) -> str:
        """Narrate a station-maintenance or roll action (action tuple from
        the autopilot scan)."""
        kind = action[0]
        balance = self.ledger.player_balance(self.player.game_player_id)
        pens = self.station.get_total_pens(self.player.game_player_id)

        if kind == "mortgage":
            pn = action[2]
            return (f"Cash is tight (${balance:,}) — mortgaging paddock {pn} "
                    f"to free up funds.")
        if kind == "debt_recovery":
            step = self.find_debt_recovery_step()
            if step and step[0] == "sheep":
                return (f"${-balance:,} in the red — selling {step[1]} pen(s) "
                        f"to the bank to settle the debt.")
            if step and step[0] == "haystack":
                return f"${-balance:,} in the red — selling the haystack to settle up."
            if step and step[0] == "ram":
                return f"${-balance:,} in the red — selling a stud ram to settle up."
            if step and step[0] == "mortgage":
                return f"${-balance:,} in the red — mortgaging a paddock to settle up."
            return f"${-balance:,} in the red — raising cash to settle the debt."
        if kind == "lift_mortgage":
            pn = action[2]
            return (f"Flush at ${balance:,} — lifting the mortgage on paddock {pn} "
                    f"to get it earning again.")
        if kind == "upgrade":
            pn, target = action[2], action[3]
            return (f"Building the station — upgrading paddock {pn} to {target} "
                    f"to grow toward the 30-pen win.")

        # kind == "roll": explain what was weighed and why it's just rolling.
        if self.difficulty == "easy":
            return f"{self._name()} sizes up the board and rolls."
        # Narrate intent without revealing the AI's internal thresholds —
        # vague "needs more cash", never the exact cushion/limit figures.
        bits = []
        if self.player.is_in_drought:
            bits.append("in drought, so holding off on upgrades and restocking")
        else:
            imp = self.station.can_upgrade_to_improved(self.player.game_player_id)
            irr = self.station.can_upgrade_to_irrigated(self.player.game_player_id)
            buffer = self.t["upgrade_cash_buffer"] + self._cash_reserve_extra()
            if irr.get("can_upgrade") and balance < IRRIGATED_PASTURE_COST + buffer:
                bits.append("would like to irrigate but needs more cash first")
            elif imp.get("can_upgrade") and balance < IMPROVED_PASTURE_COST + buffer:
                bits.append("would like to improve a paddock but needs more cash first")
        mortgaged = [p for p in self.station.get_paddocks(self.player.game_player_id)
                     if p.is_mortgaged]
        if mortgaged and balance < self.t["lift_mortgage_cash_floor"]:
            bits.append("wants to lift a mortgage but needs more cash first")
        reason = "; ".join(bits) if bits else "station's in good order"
        return f"{self._name()}: {reason} — rolling the dice."

    def pending_thinking_summary(self, pending: models.PendingAction) -> str:
        """Narrate how the AI is leaning on a pending decision."""
        data = json.loads(pending.action_data) if pending.action_data else {}
        at = pending.action_type
        balance = self.ledger.player_balance(self.player.game_player_id)
        pens = self.station.get_total_pens(self.player.game_player_id)

        if at == "stock_sale_decision":
            if self.difficulty == "easy":
                return f"{self._name()} mulls the stock sale."
            if bool(data.get("in_drought")):
                return ("In drought — Natural/Improved would sell at half price, "
                        "so leaning toward passing.")
            if pens < self.t["buy_threshold_pens"] and balance >= self.t["buy_floor_cash"]:
                return "Still room to grow the flock — looking to buy more stock."
            if pens >= self.t["sell_threshold_pens"]:
                return "Well stocked up — weighing a sell to bank the cash."
            return "Holding back — likely to pass this stock sale."
        if at == "stud_ram_purchase":
            price = int(data.get("purchase_price", 0) or 0)
            if self.difficulty == "easy":
                return f"{self._name()} eyes the stud ram (${price:,})."
            affordable = balance >= price + self.t["stud_ram_cash_buffer"]
            enough_pens = pens >= self.t["stud_ram_min_pens"]
            if affordable and enough_pens and not self.player.is_in_drought:
                return f"A stud ram for ${price:,} would lift the wool cheques — inclined to buy."
            if not enough_pens:
                return ("A stud ram's on offer, but the flock's too small to make "
                        "it pay — likely passing.")
            return f"A stud ram for ${price:,} is tempting, but needs more cash — likely passing."
        if at == "expense_payment":
            if data.get("alternative_payment"):
                return "Choosing how to treat the flock for worms."
            cost = int(data.get("total_cost", 0) or 0)
            return f"Settling a ${cost:,} expense."
        if at == "tucker_bag_drawn":
            return f"{self._name()} reads the Tucker Bag card."
        if at in ("fire_fighting_offer", "fire_fighting_auction"):
            return "Sizing up the fire-fighting equipment on offer."
        if at == "debt_settlement":
            return f"${-balance:,} in debt — raising cash before play can continue."
        # Informational acknowledgements (wool cheque, drought result, etc.)
        return f"{self._name()} reviews what just happened."

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

        if action_type == "debt_settlement":
            return self._settle_debt(pending)
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
            return self._fire_fighting_auction(data)

        # Everything else is purely informational — acknowledge.
        try:
            self.decision.acknowledge(self.player.game_player_id)
        except ValueError:
            pass
        return f"{action_type}:acknowledged"

    # ── Station maintenance (between rolls) ────────────────────────────
    def find_upgrade_candidate(self) -> dict | None:
        """If the AI should upgrade a paddock RIGHT NOW (it's their turn,
        no pending action), return {'paddock_number': N, 'target_type': T}.
        Returns None for Easy difficulty, when in drought, or when no
        affordable upgrade is available.
        Rule: upgrades only on own turn — caller must check that.
        Rule: a Player in drought cannot upgrade paddocks."""
        if self.difficulty == "easy":
            return None
        if self.player.is_in_drought:
            return None

        balance = self.ledger.player_balance(self.player.game_player_id)
        buffer = self.t["upgrade_cash_buffer"] + self._cash_reserve_extra()

        # Improved → Irrigated (only when all 5 are already improved/irrigated)
        irr_info = self.station.can_upgrade_to_irrigated(self.player.game_player_id)
        if irr_info["can_upgrade"] and balance >= IRRIGATED_PASTURE_COST + buffer:
            paddocks = self.station.get_paddocks(self.player.game_player_id)
            improved = [p for p in paddocks if p.paddock_type == "improved" and not p.is_mortgaged]
            if improved:
                # Upgrade the first one (lowest paddock number).
                return {"paddock_number": improved[0].paddock_number, "target_type": "irrigated"}

        # Natural → Improved
        imp_info = self.station.can_upgrade_to_improved(self.player.game_player_id)
        if imp_info["can_upgrade"] and balance >= IMPROVED_PASTURE_COST + buffer:
            paddock_no = imp_info["available_paddocks"][0]
            return {"paddock_number": paddock_no, "target_type": "improved"}

        return None

    def find_mortgage_candidate(self) -> int | None:
        """Mortgage when cash is low and total stock <= 8 pens (game rule).
        Two trigger modes:
          - Normal cash crunch: balance below mortgage_cash_floor — mortgage
            a low-tier empty paddock to top up.
          - Stuck recovery: barely any pens AND barely any cash — mortgage
            aggressively (including Irrigated as last resort) to give the
            AI cash to buy stock with at the next Stock Sale.
        Returns paddock_number or None."""
        if self.difficulty == "easy":
            return None
        balance = self.ledger.player_balance(self.player.game_player_id)
        total_pens = self.station.get_total_pens(self.player.game_player_id)
        if total_pens > 8:  # game rule
            return None
        stuck = self._is_stuck()
        if balance >= self.t["mortgage_cash_floor"] and not stuck:
            return None
        paddocks = [p for p in self.station.get_paddocks(self.player.game_player_id)
                    if not p.is_mortgaged]
        if not paddocks:
            return None
        if stuck:
            # Prefer Natural/Improved over Irrigated (preserve the win path);
            # within each tier, lowest paddock number first.
            naturals_improved = [p for p in paddocks if p.paddock_type in ("natural", "improved")]
            pool = naturals_improved if naturals_improved else paddocks
            tier_rank = {"natural": 0, "improved": 1, "irrigated": 2}
            pool.sort(key=lambda p: (tier_rank[p.paddock_type], p.paddock_number))
            return pool[0].paddock_number
        # Normal cash crunch: empty paddocks first, lowest tier first.
        tier_rank = {"natural": 0, "improved": 1, "irrigated": 2}
        paddocks.sort(key=lambda p: (
            p.sheep_pens > 0,        # empty first
            tier_rank[p.paddock_type],  # then by tier
            p.paddock_number,
        ))
        return paddocks[0].paddock_number

    def find_lift_mortgage_candidate(self) -> int | None:
        """Lift a mortgage when cash is comfortable. Prefer highest-tier
        paddocks first (recover the most valuable asset). Cost = mortgage
        value × 1.10."""
        if self.difficulty == "easy":
            return None
        if self._is_stuck():
            return None  # don't undo the recovery while stuck
        balance = self.ledger.player_balance(self.player.game_player_id)
        floor = self.t["lift_mortgage_cash_floor"]
        mortgaged = [p for p in self.station.get_paddocks(self.player.game_player_id)
                     if p.is_mortgaged]
        if not mortgaged:
            return None
        # Lift selection priority: irrigated → improved → natural.
        tier_rank = {"natural": 2, "improved": 1, "irrigated": 0}
        mortgaged.sort(key=lambda p: (tier_rank[p.paddock_type], p.paddock_number))
        mortgage_values = {
            "natural": MORTGAGE_NATURAL,
            "improved": MORTGAGE_IMPROVED,
            "irrigated": MORTGAGE_IRRIGATED,
        }
        for p in mortgaged:
            cost = int(mortgage_values[p.paddock_type] * (1 + MORTGAGE_INTEREST_RATE))
            if balance >= cost + floor:
                return p.paddock_number
        return None

    def find_debt_recovery_step(self) -> tuple | None:
        """When in debt (negative balance blocks rolling), pick ONE
        liquidation step toward solvency: sell sheep first (just enough at
        the emergency price), then the haystack, then a stud ram. Applies
        to every difficulty — Easy must recover too. Mortgaging is handled
        by find_mortgage_candidate (checked before this by the autopilot).
        Returns ('sheep', pens) | ('haystack',) | ('ram', space_id) | None."""
        balance = self.ledger.player_balance(self.player.game_player_id)
        if balance >= 0:
            return None
        total_pens = self.station.get_total_pens(self.player.game_player_id)
        if total_pens > 0:
            needed = -balance
            pens = min(total_pens,
                       -(-needed // EMERGENCY_SELL_PRICE_PER_PEN))  # ceil div
            return ("sheep", pens)
        if self.player.haystack_pasture:
            return ("haystack", "pasture")
        if self.player.haystack_irrigated:
            return ("haystack", "irrigated")
        rams = self.station.get_stud_rams_owned(self.player.game_player_id)
        if rams:
            return ("ram", rams[0].space_id)
        # No stock left (pens are 0 here, so the 8-pen mortgage rule is
        # satisfied) — mortgage paddocks, lowest tier first.
        unmortgaged = [p for p in self.station.get_paddocks(self.player.game_player_id)
                       if not p.is_mortgaged]
        if unmortgaged:
            tier_rank = {"natural": 0, "improved": 1, "irrigated": 2}
            unmortgaged.sort(key=lambda p: (tier_rank[p.paddock_type], p.paddock_number))
            return ("mortgage", unmortgaged[0].paddock_number)
        return None

    def execute_debt_recovery(self, step: tuple) -> str:
        """Perform one liquidation step (mirrors the human station routes)."""
        latest_turn = (
            self.session.query(models.Turn)
            .filter_by(game_id=self.game_id)
            .order_by(models.Turn.turn_id.desc())
            .first()
        )
        turn_id = latest_turn.turn_id if latest_turn else None

        if step[0] == "sheep":
            pens = step[1]
            self.station.sell_sheep(self.player.game_player_id, pens)
            income = pens * EMERGENCY_SELL_PRICE_PER_PEN
            self.ledger.receive_from_bank(
                self.player, income, "emergency_sale", turn_id,
                notes=f"Emergency sold {pens} pens at "
                      f"${EMERGENCY_SELL_PRICE_PER_PEN}/pen (debt)")
            self.session.flush()
            return f"debt_recovery:sold_{pens}_pens"

        if step[0] == "haystack":
            haystack_type = step[1]
            attr = "haystack_pasture" if haystack_type == "pasture" else "haystack_irrigated"
            self.ledger.receive_from_bank(
                self.player, HAYSTACK_SELL_PRICE, "haystack_sale", turn_id,
                notes=f"Sold {haystack_type} haystack (debt)")
            setattr(self.player, attr, False)
            self.session.flush()
            return "debt_recovery:sold_haystack"

        if step[0] == "mortgage":
            return self.execute_mortgage(step[1])

        # step[0] == "ram"
        space_id = step[1]
        ram_state = self.session.query(models.StudRamState).filter_by(
            game_id=self.game_id, space_id=space_id,
            owner_game_player_id=self.player.game_player_id,
        ).first()
        if ram_state:
            self.ledger.receive_from_bank(
                self.player, STUD_RAM_SELL_PRICE, "stud_ram_sale", turn_id,
                notes="Sold stud ram (debt)")
            ram_state.owner_game_player_id = None
            ram_state.is_available = True
            self.session.flush()
        return "debt_recovery:sold_ram"

    def _settle_debt(self, pending: models.PendingAction) -> str:
        """The debt gate blocks the whole game — liquidate one asset per
        tick (paced like other AI moves) until solvent, then resolve the
        pending. If nothing is left to sell, re-run the debt check, which
        declares bankruptcy rather than deadlocking the game."""
        from app.services.bankruptcy_service import BankruptcyService
        bankruptcy = BankruptcyService(self.session, self.game_id)
        step = self.find_debt_recovery_step()
        if step is not None:
            tag = self.execute_debt_recovery(step)
            bankruptcy.clear_debt_pending_if_solvent(self.player.game_player_id)
            return tag
        # Already solvent (e.g. a trade came through), or truly out of assets.
        if not bankruptcy.clear_debt_pending_if_solvent(self.player.game_player_id):
            bankruptcy.check_debt(self.player, pending.turn_id)
        return "debt_settlement:checked"

    def execute_mortgage(self, paddock_number: int) -> str:
        """Mortgage the paddock and credit the player."""
        latest_turn = (
            self.session.query(models.Turn)
            .filter_by(game_id=self.game_id)
            .order_by(models.Turn.turn_id.desc())
            .first()
        )
        turn_id = latest_turn.turn_id if latest_turn else None
        amount = self.station.mortgage_paddock(self.player.game_player_id, paddock_number)
        self.ledger.receive_from_bank(
            self.player, amount, "mortgage", turn_id,
            notes=f"Mortgaged paddock {paddock_number}",
        )
        self.session.flush()
        return f"mortgage:{paddock_number}"

    def execute_lift_mortgage(self, paddock_number: int) -> str:
        """Pay mortgage + 10% interest and clear the mortgage flag.
        Triggers a win check (clearing the last mortgage on a 30-pen
        irrigated station = win)."""
        paddock = next(
            (p for p in self.station.get_paddocks(self.player.game_player_id)
             if p.paddock_number == paddock_number),
            None,
        )
        if not paddock:
            return "lift_mortgage:not_found"
        mortgage_values = {
            "natural": MORTGAGE_NATURAL,
            "improved": MORTGAGE_IMPROVED,
            "irrigated": MORTGAGE_IRRIGATED,
        }
        repay_cost = int(mortgage_values[paddock.paddock_type] * (1 + MORTGAGE_INTEREST_RATE))
        latest_turn = (
            self.session.query(models.Turn)
            .filter_by(game_id=self.game_id)
            .order_by(models.Turn.turn_id.desc())
            .first()
        )
        turn_id = latest_turn.turn_id if latest_turn else None
        self.ledger.pay_bank(
            self.player, repay_cost, "unmortgage", turn_id,
            notes=f"Unmortgaged paddock {paddock_number}",
        )
        self.station.unmortgage_paddock(self.player.game_player_id, paddock_number)
        self.station.declare_winner_if_eligible(self.player.game_player_id, turn_id)
        self.session.flush()
        return f"lift_mortgage:{paddock_number}"

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
        """If a useful haystack is on offer and the AI should buy it given its
        difficulty + cash, do so inline. Buys one type per call (the most
        relevant); a second can be picked up at a later Haymaking landing.
        Returns True if bought."""
        offers = data.get("haystack_offers") or []
        if not offers:
            return False
        # Prefer the pasture haystack while in drought (Local Drought hits
        # Natural/Improved); otherwise take pasture first, then irrigated.
        order = ["pasture", "irrigated"]
        offer = next((o for t in order for o in offers if o["type"] == t), None)
        if offer is None:
            return False
        haystack_type = offer["type"]
        attr = "haystack_pasture" if haystack_type == "pasture" else "haystack_irrigated"
        if getattr(self.player, attr):
            return False
        cost = int(offer.get("cost") or 0)
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
            # Medium / Hard: buy when comfortably affordable. Always grab one
            # if in drought (already paying the premium means we badly need
            # offset capacity for future drought sales).
            if self.player.is_in_drought:
                buffer = 0
            else:
                buffer = self.t["haystack_cash_buffer"] + self._cash_reserve_extra()
            if balance < cost + buffer:
                return False

        latest_turn = (
            self.session.query(models.Turn)
            .filter_by(game_id=self.game_id)
            .order_by(models.Turn.turn_id.desc())
            .first()
        )
        turn_id = latest_turn.turn_id if latest_turn else None
        notes = (f"Bought {haystack_type} haystack"
                 + (" (drought premium)" if self.player.is_in_drought else ""))
        self.ledger.pay_bank(self.player, cost, "haystack_purchase", turn_id, notes=notes)
        setattr(self.player, attr, True)
        self.session.flush()
        return True

    # "Stuck" recovery — AI has barely any pens AND barely any cash, so
    # going round the board just bleeds it further. Mortgage paddocks
    # (including Irrigated as last resort) to raise cash, then spend
    # whatever was raised on sheep at the next Stock Sale.
    STUCK_PENS_THRESHOLD = 3
    STUCK_CASH_THRESHOLD = 600

    def _is_stuck(self) -> bool:
        total_pens = self.station.get_total_pens(self.player.game_player_id)
        balance = self.ledger.player_balance(self.player.game_player_id)
        return total_pens < self.STUCK_PENS_THRESHOLD and balance < self.STUCK_CASH_THRESHOLD

    def _has_retained_card_by_effect(self, effect_code: str) -> bool:
        return (
            self.session.query(models.CardDraw)
            .join(models.Card, models.CardDraw.card_id == models.Card.card_id)
            .filter(
                models.CardDraw.game_id == self.game_id,
                models.CardDraw.kept_by_player_id == self.player.game_player_id,
                models.CardDraw.discarded_at.is_(None),
                models.Card.effect_code == effect_code,
            )
            .first()
        ) is not None

    def _drought_imminent(self) -> bool:
        """True (Hard only) when a Local Drought space lies within the
        AI's lookahead window. Adds a cash-reserve cushion before any
        cash-spending decision."""
        if self.difficulty != "hard":
            return False
        lookahead = self.t.get("drought_lookahead_spaces", 0)
        if lookahead <= 0:
            return False
        pos = self.player.current_board_index or 0
        for offset in range(1, lookahead + 1):
            target = (pos + offset) % BOARD_SIZE
            if target in LOCAL_DROUGHT_BOARD_INDICES:
                return True
        return False

    def _cash_reserve_extra(self) -> int:
        """Extra cash buffer to require when drought is imminent (Hard)."""
        return self.t.get("drought_extra_buffer", 0) if self._drought_imminent() else 0

    def _stock_buy_price_range(self) -> tuple:
        """(min, max) buy price per pen across the Stock Sale deck. This is
        public knowledge (printed on the cards) — not a peek at the draw."""
        lo, hi = (
            self.session.query(
                func.min(models.StockCard.buy_price_per_pen),
                func.max(models.StockCard.buy_price_per_pen),
            ).one()
        )
        return int(lo or 0), int(hi or 0)

    def _buy_cash_reserve(self) -> int:
        """Cash to keep in hand after buying stock. Waived during stuck
        recovery, where every dollar raised by mortgaging should become
        sheep. Includes Hard's drought-imminent buffer when applicable.
        Best-effort: the price is revealed only after committing, so a
        pricier-than-best-case card may still dip into the cushion."""
        if self._is_stuck():
            return 0
        return self.t.get("buy_cash_reserve", 0) + self._cash_reserve_extra()

    def _buy_with_affordability_retry(self, qty: int) -> str | None:
        """Commit to buying qty pens. The price is revealed only after the
        commit; if it makes qty unaffordable, retry once at the maximum
        affordable count (allowed — retries may only reduce), and pass if
        even one pen is out of reach. Always resolves the pending action
        when a commit happened. Returns a result tag, or None if the buy
        was rejected before committing (caller decides what to do next)."""
        try:
            result = self.decision.stock_sale_buy(
                self.player.game_player_id, qty, use_high_stock_prices=False
            )
        except ValueError:
            return None
        if result.get("status") != "insufficient_funds":
            return f"stock_sale:bought_{qty}"

        # Reduce to what the locked price allows while keeping the cash
        # cushion intact (max_affordable_pens is the absolute rules limit).
        buy_price = int(result.get("buy_price") or 0)
        spendable = max(0, int(result.get("balance") or 0) - self._buy_cash_reserve())
        affordable = spendable // buy_price if buy_price > 0 else 0
        affordable = min(affordable, int(result.get("max_affordable_pens") or 0))
        if 1 <= affordable < qty:
            try:
                result = self.decision.stock_sale_buy(
                    self.player.game_player_id, affordable, use_high_stock_prices=False
                )
                if result.get("status") != "insufficient_funds":
                    return f"stock_sale:bought_{affordable}_reduced"
            except ValueError:
                pass
        # Can't afford even one pen at the locked price — pass out.
        self.decision.stock_sale_pass(self.player.game_player_id)
        return "stock_sale:cant_afford_passed"

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
            # Don't gamble on a price we can't cover even on the cheapest
            # card, and keep the cash cushion.
            min_price, _ = self._stock_buy_price_range()
            balance = self.ledger.player_balance(self.player.game_player_id)
            spendable = max(0, balance - self._buy_cash_reserve())
            if min_price > 0:
                pens = min(pens, spendable // min_price)
            tag = self._buy_with_affordability_retry(pens) if pens >= 1 else None
            if tag is None:
                # Rejected before committing (no space / blocked) — pass.
                self.decision.stock_sale_pass(self.player.game_player_id)
                return "stock_sale:buy_failed_passed"
            return tag

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

        # PRIORITY 1 — Buy toward the 30-pen win condition. Keep buying
        # whenever there's room, cash above the floor, and we're under
        # the per-difficulty target. If "stuck" (low pens + low cash),
        # drop the floor to $0 so the AI spends the cash it just raised
        # by mortgaging on any pens it can afford.
        cash_floor = 0 if self._is_stuck() else self.t["buy_floor_cash"]
        if (buy_capacity >= 1
                and total_pens < self.t["buy_threshold_pens"]
                and balance >= cash_floor):
            qty = min(self.t.get("buy_qty", 5), buy_capacity, max_per_txn)
            # Never commit to more pens than the cheapest possible card
            # allows after keeping the cash cushion — the price is revealed
            # only after committing, and a commit can be reduced but not
            # abandoned for a sell.
            min_price, _ = self._stock_buy_price_range()
            spendable = max(0, balance - self._buy_cash_reserve())
            if min_price > 0:
                qty = min(qty, spendable // min_price)
            if qty >= 1:
                tag = self._buy_with_affordability_retry(qty)
                if tag:
                    return tag

        # PRIORITY 2 — Sell only when very full or to burn an HSP card.
        # Without HSP, we want the pens for the win, not the cash from a sale.
        sell_threshold = (self.t["sell_threshold_pens_hsp"] if has_hsp
                          else self.t["sell_threshold_pens"])
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

        self.decision.stock_sale_pass(self.player.game_player_id)
        return "stock_sale:passed"

    def _stud_ram_purchase_medium(self, data: dict) -> str:
        price = int(data.get("purchase_price", 0) or 0)
        balance = self.ledger.player_balance(self.player.game_player_id)
        total_pens = self.station.get_total_pens(self.player.game_player_id)
        in_drought = bool(self.player.is_in_drought)
        # Buy if comfortably affordable, not in drought, and we have enough
        # sheep for the wool bonus to pay back.
        if (balance >= price + self.t["stud_ram_cash_buffer"] + self._cash_reserve_extra()
                and not in_drought
                and total_pens >= self.t["stud_ram_min_pens"]):
            try:
                self.decision.stud_ram_buy(self.player.game_player_id)
                return "stud_ram:bought"
            except ValueError:
                pass
        self.decision.stud_ram_pass(self.player.game_player_id)
        return "stud_ram:passed"

    def _fire_fighting_auction(self, data: dict) -> str:
        # Hard bids up to ffe_max_bid. Easy/Medium auto-decline.
        if self.difficulty != "hard":
            try:
                self.decision.fire_fighting_auction_decline(self.player.game_player_id)
            except ValueError:
                pass
            return "fire_fighting_auction:declined"

        # Already hold FFE? Decline.
        if self._has_retained_card_by_effect("FIRE_FIGHTING_EQUIPMENT"):
            try:
                self.decision.fire_fighting_auction_decline(self.player.game_player_id)
            except ValueError:
                pass
            return "ffe_auction:already_have"

        # Already current high bidder? Wait (don't outbid self).
        if data.get("current_bidder_id") == self.player.game_player_id:
            return "ffe_auction:already_leading"

        current_bid = data.get("current_bid")
        starting_price = int(data.get("starting_price", 350) or 350)
        increment = int(self.t.get("ffe_bid_increment", 50))
        next_bid = max(starting_price, (current_bid or 0) + increment)

        max_bid = int(self.t.get("ffe_max_bid", 0))
        buffer = int(self.t.get("ffe_cash_buffer", 0)) + self._cash_reserve_extra()
        balance = self.ledger.player_balance(self.player.game_player_id)
        if next_bid > max_bid or balance < next_bid + buffer:
            try:
                self.decision.fire_fighting_auction_decline(self.player.game_player_id)
            except ValueError:
                pass
            return f"ffe_auction:declined_over_budget_{next_bid}"

        try:
            self.decision.fire_fighting_auction_bid(self.player.game_player_id, next_bid)
            return f"ffe_auction:bid_{next_bid}"
        except ValueError:
            try:
                self.decision.fire_fighting_auction_decline(self.player.game_player_id)
            except ValueError:
                pass
            return "ffe_auction:bid_failed_declined"

    def _expense_payment_medium(self, data: dict) -> str:
        if data.get("alternative_payment"):
            # Drench Sheep for Worms: enhanced grants +20% next sell bonus
            # and the Worm Control card. Worth it when we have stock and cash.
            total_pens = int(data.get("total_pens", 0) or 0)
            balance = self.ledger.player_balance(self.player.game_player_id)
            enhanced_cost = data.get("enhanced_option", {}).get("cost", 0) or 0
            choose_enhanced = (
                total_pens >= self.t["drench_enhanced_min_pens"]
                and balance >= enhanced_cost + self.t["drench_enhanced_cash_buffer"] + self._cash_reserve_extra()
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
