# app/services/decision_service.py
import json
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app import models
from app.services.ledger_service import LedgerService
from app.services.station_service import StationService
from app.services.stock_sale_service import StockSaleService
from app.services.card_service import CardService
from app.services.drought_service import DroughtService


class DecisionService:
    def __init__(self, session: Session, game_id: int):
        self.session = session
        self.game_id = game_id
        self.ledger = LedgerService(session, game_id)
        self.station = StationService(session, game_id)
        self.stock_sale = StockSaleService(session, game_id)
        self.drought = DroughtService(session, game_id)

    def get_pending_action(self) -> Optional[models.PendingAction]:
        """Get current unresolved pending action for the game.

        Oldest first so multi-pending turns (e.g. pass-through wool cheque +
        destination-space action) surface in the order they were created.
        """
        return (
            self.session.query(models.PendingAction)
            .filter(
                models.PendingAction.game_id == self.game_id,
                models.PendingAction.resolved_at.is_(None),
            )
            .order_by(models.PendingAction.pending_action_id.asc())
            .first()
        )

    def get_pending_action_state(self) -> Optional[dict]:
        """Get current pending action state for frontend display."""
        pending = self.get_pending_action()
        if not pending:
            return None

        result = {
            "action_type": pending.action_type,
            "active_player_id": pending.active_player_id,
            "turn_id": pending.turn_id,
        }

        if pending.action_data:
            data = json.loads(pending.action_data)

            # Dynamically update haystack availability and price based on current player state
            if data.get("haystack_available"):
                from app.constants import haystack_buy_price
                player = self.session.query(models.GamePlayer).get(pending.active_player_id)
                if player and player.has_haystack:
                    data["haystack_available"] = False
                elif player:
                    data["haystack_cost"] = haystack_buy_price(player)
                    data["haystack_drought_premium"] = bool(player.is_in_drought)

            # Refresh drought + restock-block flags on the stock sale modal so
            # the UI shows the correct rules even if state changes between
            # landing and clicking.
            if pending.action_type == "stock_sale_decision":
                player = self.session.query(models.GamePlayer).get(pending.active_player_id)
                if player is not None:
                    data["in_drought"] = bool(player.is_in_drought)
                    data["restock_blocked"] = bool(player.restock_blocked_until_circuit)
                    data["restock_block_spaces_remaining"] = player.restock_block_spaces_remaining or 0
                    data["restock_block_scope"] = player.restock_block_scope
                    data["empty_natural_pens"] = self.station.get_empty_pens_by_type(pending.active_player_id, "natural")
                    data["empty_improved_pens"] = self.station.get_empty_pens_by_type(pending.active_player_id, "improved")
                    data["next_sell_price_modifier"] = player.next_sell_price_modifier or 0
                    data["balance"] = self.ledger.player_balance(pending.active_player_id)

            result["action_data"] = data

        return result

    # ── Stock Sale Decision ─────────────────────────────────────────────

    def stock_sale_buy(self, player_id: int, pens: int,
                       use_high_stock_prices: bool = False) -> dict:
        """Player buys sheep at the stock sale. The Stock Sale card is drawn
        here — AFTER the player has committed to buying — per the rules.

        Once committed, the card and (if applicable) the High Stock Prices
        modifier are locked for the whole transaction. If the player can't
        afford the requested pens at the locked price, the call returns a
        soft "insufficient_funds" status (card stays drawn, pending stays
        open) so the player can retry with a smaller amount or pass.
        """
        pending = self._validate_pending("stock_sale_decision", player_id)
        data = json.loads(pending.action_data) if pending.action_data else {}

        player = self.session.query(models.GamePlayer).get(player_id)

        # Reuse the card drawn on the first commit; lock HSP state at first commit.
        stock_card = self.stock_sale.get_card_for_turn(pending.turn_id)
        is_retry = stock_card is not None
        if is_retry:
            original = data.get("original_pens", 0)
            if pens > original:
                raise ValueError(
                    f"Already committed to {original} pens at the locked price — "
                    f"retry must be {original} or fewer"
                )
            hsp_locked = bool(data.get("hsp_locked", False))
        else:
            stock_card = self.stock_sale.draw_stock_card(pending.turn_id)
            hsp_locked = bool(use_high_stock_prices)
            data["buy_committed"] = True
            data["original_pens"] = pens
            data["hsp_locked"] = hsp_locked
            pending.action_data = json.dumps(data)
            self.session.flush()

        # Apply locked HSP setting (ignore request's flag on retry)
        hsp_modifier_pct = 0
        hsp_draw = None
        if hsp_locked:
            hsp_draw = self._find_retained_high_stock_prices(player_id)
            if not hsp_draw:
                raise ValueError("No retained High Stock Prices card to apply")
            card = self.session.query(models.Card).get(hsp_draw.card_id)
            params = json.loads(card.effect_params) if card.effect_params else {}
            hsp_modifier_pct = params.get("price_modifier_pct", 0)

        base_buy_price = stock_card.buy_price_per_pen
        buy_price = int(base_buy_price * (100 + hsp_modifier_pct) / 100) if hsp_modifier_pct \
                    else base_buy_price
        total_cost = buy_price * pens

        # Validate — insufficient funds is soft (card stays, retry allowed)
        balance = self.ledger.player_balance(player_id)
        if balance < total_cost:
            return {
                "status": "insufficient_funds",
                "requested_pens": pens,
                "balance": balance,
                "hsp_locked": hsp_locked,
            }

        # Restock scoping. Two independent restrictions can apply at once:
        # 1. Drought → buy only into Irrigated paddocks.
        # 2. Restock block → 'all' (Lucerne / Grass Fire) bars ALL buying;
        #    'irrigated' (Bore Dries Up) bars Irrigated only.
        # If drought + irrigated-block apply together, the only allowed bucket
        # is empty → must refuse.
        scope = (player.restock_block_scope or 'all') if player.restock_blocked_until_circuit else None
        if scope == 'all':
            raise ValueError("Cannot buy stock: restock blocked until next circuit")

        only_types = None
        if player.is_in_drought and scope == 'irrigated':
            raise ValueError(
                "Cannot restock: drought requires Irrigated paddocks but "
                "Bore Dries Up has blocked Irrigated restocking until next circuit"
            )
        elif player.is_in_drought:
            only_types = ("irrigated",)
            empty_pens = self.station.get_empty_pens_by_type(player_id, "irrigated")
            if empty_pens == 0:
                raise ValueError(
                    "Cannot restock during drought — Natural and Improved pasture "
                    "are blocked, and no Irrigated capacity is available"
                )
            if pens > empty_pens:
                raise ValueError(
                    f"Drought restricts restocking to Irrigated only — {empty_pens} pen(s) available"
                )
        elif scope == 'irrigated':
            # Bore Dries Up — buy into Natural/Improved only.
            only_types = ("natural", "improved")
            empty_pens = (
                self.station.get_empty_pens_by_type(player_id, "natural")
                + self.station.get_empty_pens_by_type(player_id, "improved")
            )
            if empty_pens == 0:
                raise ValueError(
                    "Cannot restock — Bore Dries Up blocks Irrigated restocking "
                    "and you have no Natural/Improved capacity available"
                )
            if pens > empty_pens:
                raise ValueError(
                    f"Bore Dries Up blocks Irrigated restocking — only "
                    f"{empty_pens} pen(s) of Natural/Improved capacity available"
                )
        else:
            empty_pens = self.station.get_empty_pens(player_id)
            if pens > empty_pens:
                raise ValueError(f"Not enough paddock space: {empty_pens} pens available")

        from app.constants import MAX_PENS_PER_TRANSACTION
        if pens > MAX_PENS_PER_TRANSACTION:
            raise ValueError(f"Cannot buy more than {MAX_PENS_PER_TRANSACTION} pens per transaction")

        # Execute purchase
        notes = f"Bought {pens} pens at ${buy_price}/pen"
        if hsp_modifier_pct:
            notes += f" (+{hsp_modifier_pct}% High Stock Prices)"
        if only_types == ("irrigated",):
            notes += " (drought: irrigated only)"
        elif only_types == ("natural", "improved"):
            notes += " (bore dried up: natural/improved only)"
        self.ledger.pay_bank(player, total_cost, "stock_purchase", pending.turn_id, notes=notes)
        self.station.buy_sheep(player_id, pens, only_types=only_types)

        # Win check after every stock acquisition.
        self.station.declare_winner_if_eligible(player_id, pending.turn_id)

        # Discard High Stock Prices card on use
        if hsp_draw:
            hsp_draw.kept_by_player_id = None
            hsp_draw.discarded_at = func.now()
            self.session.flush()

        self._resolve(pending)

        # Result step — show the revealed card and outcome to the player.
        self._create_pending_stock_sale_result(pending.turn_id, player, {
            "action": "buy",
            "pens": pens,
            "total_cost": total_cost,
            "buy_price": buy_price,
            "card": {
                "buy_price_per_pen": stock_card.buy_price_per_pen,
                "sell_price_natural": stock_card.sell_price_natural,
                "sell_price_improved_irrigated": stock_card.sell_price_improved_irrigated,
            },
            "high_stock_prices_applied": bool(hsp_modifier_pct),
        })

        return {"status": "bought", "pens": pens, "total_cost": total_cost,
                "high_stock_prices_applied": bool(hsp_modifier_pct),
                "card": {
                    "buy_price_per_pen": stock_card.buy_price_per_pen,
                    "sell_price_natural": stock_card.sell_price_natural,
                    "sell_price_improved_irrigated": stock_card.sell_price_improved_irrigated,
                }}

    def stock_sale_sell(self, player_id: int, pens: int,
                        use_high_stock_prices: bool = False,
                        use_auto_sell_modifier: bool = True) -> dict:
        """Player sells sheep at the stock sale. The Stock Sale card is drawn
        here — AFTER the player has committed to selling — per the rules.

        use_auto_sell_modifier: when False, the player chooses NOT to consume
        their pending next_sell_price_modifier (from Worm Control Programme /
        Control of Weeds and Insects / Fertilised Pasture). The modifier is
        preserved for a future sell.
        """
        pending = self._validate_pending("stock_sale_decision", player_id)
        data = json.loads(pending.action_data) if pending.action_data else {}
        if data.get("buy_committed"):
            raise ValueError(
                "Already committed to buy — cannot switch to sell. "
                "Reduce the pens count or pass."
            )

        player = self.session.query(models.GamePlayer).get(player_id)
        stock_card = self.stock_sale.draw_stock_card(pending.turn_id)

        # Determine sell price based on paddock types
        total_pens = self.station.get_total_pens(player_id)
        if pens > total_pens:
            raise ValueError(f"Cannot sell more than you have: {total_pens} pens owned")

        from app.constants import MAX_PENS_PER_TRANSACTION
        if pens > MAX_PENS_PER_TRANSACTION:
            raise ValueError(f"Cannot sell more than {MAX_PENS_PER_TRANSACTION} pens per transaction")

        # Auto-apply expense-bonus modifier (from Spray Weeds / Fertilising spaces)
        # unless the player elected to save it for a later sale.
        auto_modifier = (player.next_sell_price_modifier or 0) if use_auto_sell_modifier else 0

        # Optional: apply retained High Stock Prices card on top
        hsp_draw = None
        hsp_modifier_pct = 0
        if use_high_stock_prices:
            hsp_draw = self._find_retained_high_stock_prices(player_id)
            if not hsp_draw:
                raise ValueError("No retained High Stock Prices card to apply")
            card = self.session.query(models.Card).get(hsp_draw.card_id)
            params = json.loads(card.effect_params) if card.effect_params else {}
            hsp_modifier_pct = params.get("price_modifier_pct", 0)

        modifier_pct = auto_modifier + hsp_modifier_pct

        breakdown = self._calculate_sell_income(player_id, pens, stock_card, modifier_pct,
                                                in_drought=bool(player.is_in_drought))
        sell_income = breakdown["total"]

        # Remove sheep in the same tier order so the income reflects what was actually sold.
        for tier_type, tier_pens in breakdown["tiers"]:
            if tier_pens > 0:
                self.station.sell_sheep(player_id, tier_pens, from_type=tier_type)

        notes = f"Sold {pens} pens"
        if modifier_pct:
            notes += f" (+{modifier_pct}%)"
        if player.is_in_drought:
            notes += " (drought: Natural/Improved at half price)"
        self.ledger.receive_from_bank(player, sell_income, "stock_sale", pending.turn_id, notes=notes)

        # Clear auto-apply modifier ONLY when it was consumed for this sale;
        # opting out preserves it for a later sale.
        if auto_modifier and player.next_sell_price_modifier:
            player.next_sell_price_modifier = 0
            self.session.flush()

        # Discard High Stock Prices card on use
        if hsp_draw:
            hsp_draw.kept_by_player_id = None
            hsp_draw.discarded_at = func.now()
            self.session.flush()

        self._resolve(pending)

        self._create_pending_stock_sale_result(pending.turn_id, player, {
            "action": "sell",
            "pens": pens,
            "total_income": sell_income,
            "tiers": breakdown["tiers"],
            "card": {
                "buy_price_per_pen": stock_card.buy_price_per_pen,
                "sell_price_natural": stock_card.sell_price_natural,
                "sell_price_improved_irrigated": stock_card.sell_price_improved_irrigated,
            },
            "modifier_pct": modifier_pct,
            "in_drought": bool(player.is_in_drought),
            "high_stock_prices_applied": bool(hsp_modifier_pct),
        })

        return {"status": "sold", "pens": pens, "total_income": sell_income,
                "high_stock_prices_applied": bool(hsp_modifier_pct),
                "card": {
                    "buy_price_per_pen": stock_card.buy_price_per_pen,
                    "sell_price_natural": stock_card.sell_price_natural,
                    "sell_price_improved_irrigated": stock_card.sell_price_improved_irrigated,
                }}

    def _create_pending_stock_sale_result(self, turn_id, player, data):
        action = models.PendingAction(
            game_id=self.game_id,
            turn_id=turn_id,
            action_type="stock_sale_result",
            active_player_id=player.game_player_id,
            action_data=json.dumps(data),
        )
        self.session.add(action)
        self.session.flush()

    def _find_retained_high_stock_prices(self, player_id: int):
        return (
            self.session.query(models.CardDraw)
            .join(models.Card, models.CardDraw.card_id == models.Card.card_id)
            .filter(
                models.CardDraw.game_id == self.game_id,
                models.CardDraw.kept_by_player_id == player_id,
                models.CardDraw.discarded_at.is_(None),
                models.Card.effect_code == "HIGH_STOCK_PRICES",
            )
            .order_by(models.CardDraw.draw_order.asc())
            .first()
        )

    def stock_sale_pass(self, player_id: int) -> dict:
        """Player passes on the stock sale."""
        pending = self._validate_pending("stock_sale_decision", player_id)
        self._resolve(pending)
        return {"status": "passed"}

    # ── Stud Ram Purchase ───────────────────────────────────────────────

    def stud_ram_buy(self, player_id: int) -> dict:
        """Player buys the stud ram."""
        pending = self._validate_pending("stud_ram_purchase", player_id)
        data = json.loads(pending.action_data)

        player = self.session.query(models.GamePlayer).get(player_id)
        price = data["purchase_price"]

        balance = self.ledger.player_balance(player_id)
        if balance < price:
            raise ValueError(f"Insufficient funds: need ${price}, have ${balance}")

        # Execute purchase
        self.ledger.pay_bank(player, price, "stud_ram_purchase", pending.turn_id,
                            space_id=data["space_id"],
                            notes=f"Purchased {data['space_name']}")

        ram_state = (
            self.session.query(models.StudRamState)
            .filter_by(game_id=self.game_id, space_id=data["space_id"])
            .first()
        )
        if ram_state:
            ram_state.owner_game_player_id = player_id
            ram_state.is_available = False

        self.session.flush()
        self._resolve(pending)
        return {"status": "purchased", "ram_name": data["space_name"], "price": price}

    def stud_ram_pass(self, player_id: int) -> dict:
        """Player passes on the stud ram purchase."""
        pending = self._validate_pending("stud_ram_purchase", player_id)
        self._resolve(pending)
        return {"status": "passed"}

    # ── Fire Fighting Equipment Offer (refused → other players get the chance)
    def fire_fighting_offer_respond(self, player_id: int, accept: bool) -> dict:
        pending = self._validate_pending("fire_fighting_offer", player_id)
        data = json.loads(pending.action_data)
        card = self.session.query(models.Card).get(data["card_id"])
        player = self.session.query(models.GamePlayer).get(player_id)

        if accept:
            price = data["price"]
            balance = self.ledger.player_balance(player_id)
            if balance < price:
                raise ValueError(f"Insufficient funds: need ${price}, have ${balance}")
            self.ledger.pay_bank(player, price, "card_purchase", pending.turn_id,
                                 notes=f"Purchased {card.title}")
            card_service = CardService(self.session, self.game_id)
            card_service.retain_card(player, card, pending.turn_id)
            self._resolve(pending)
            return {"status": "purchased", "price": price}

        # Declined — pass to the next queued player, if any.
        self._resolve(pending)
        queue = data.get("remaining_queue", [])
        if queue:
            next_id = queue[0]
            next_player = self.session.query(models.GamePlayer).get(next_id)
            if next_player:
                self._create_pending_action_raw(pending.turn_id, next_player,
                                                "fire_fighting_offer", {
                    "card_id": data["card_id"],
                    "card_title": data["card_title"],
                    "card_body": data["card_body"],
                    "price": data["price"],
                    "remaining_queue": queue[1:],
                })
                return {"status": "declined", "passed_to": next_player.player_name}
        return {"status": "declined", "card_returned_to_bank": True}

    # ── Fire Fighting Equipment — Open Auction (3+ player games) ────────
    def _create_fire_fighting_auction(self, turn_id, card, eligible_players, starting_price):
        action = models.PendingAction(
            game_id=self.game_id,
            turn_id=turn_id,
            action_type="fire_fighting_auction",
            active_player_id=None,
            action_data=json.dumps({
                "card_id": card.card_id,
                "card_title": card.title,
                "card_body": card.body_text,
                "starting_price": starting_price,
                "current_bid": None,
                "current_bidder_id": None,
                "current_bidder_name": None,
                "eligible_players": [
                    {"id": p.game_player_id, "name": p.player_name}
                    for p in eligible_players
                ],
                "declined": [],
            }),
        )
        self.session.add(action)
        self.session.flush()

    def fire_fighting_auction_bid(self, player_id: int, bid_amount: int) -> dict:
        pending = self.get_pending_action()
        if not pending or pending.action_type != "fire_fighting_auction":
            raise ValueError("No active fire-fighting auction")
        data = json.loads(pending.action_data)

        eligible_ids = [p["id"] for p in data["eligible_players"]]
        if player_id not in eligible_ids:
            raise ValueError("You are not part of this auction")
        if player_id in data["declined"]:
            raise ValueError("You already declined")
        if player_id == data.get("current_bidder_id"):
            raise ValueError("You are already the current high bidder")

        current_bid = data.get("current_bid")
        min_bid = data["starting_price"] if current_bid is None else current_bid + 1
        if bid_amount < min_bid:
            raise ValueError(f"Bid must be at least ${min_bid}")
        balance = self.ledger.player_balance(player_id)
        if balance < bid_amount:
            raise ValueError(f"Insufficient funds: need ${bid_amount}, have ${balance}")

        player = self.session.query(models.GamePlayer).get(player_id)
        data["current_bid"] = bid_amount
        data["current_bidder_id"] = player_id
        data["current_bidder_name"] = player.player_name
        pending.action_data = json.dumps(data)
        self.session.flush()

        outcome = self._maybe_finalize_auction(pending)
        return {"status": "bid_placed", "bid": bid_amount, "outcome": outcome}

    def fire_fighting_auction_decline(self, player_id: int) -> dict:
        pending = self.get_pending_action()
        if not pending or pending.action_type != "fire_fighting_auction":
            raise ValueError("No active fire-fighting auction")
        data = json.loads(pending.action_data)

        eligible_ids = [p["id"] for p in data["eligible_players"]]
        if player_id not in eligible_ids:
            raise ValueError("You are not part of this auction")
        if player_id in data["declined"]:
            raise ValueError("You already declined")
        if player_id == data.get("current_bidder_id"):
            raise ValueError("You cannot decline your own winning bid")

        data["declined"].append(player_id)
        pending.action_data = json.dumps(data)
        self.session.flush()

        outcome = self._maybe_finalize_auction(pending)
        return {"status": "declined", "outcome": outcome}

    def _maybe_finalize_auction(self, pending) -> str:
        """If all bidders other than the current high bidder have declined,
        award (or refund) the card and resolve. Returns one of:
        'ongoing', 'awarded', 'no_bids'."""
        data = json.loads(pending.action_data)
        eligible_ids = [p["id"] for p in data["eligible_players"]]
        declined = set(data["declined"])
        current_bidder = data.get("current_bidder_id")
        # Bidders who can still act = eligible minus declined minus current high bidder
        still_active = [
            pid for pid in eligible_ids
            if pid not in declined and pid != current_bidder
        ]
        if still_active:
            return "ongoing"

        card = self.session.query(models.Card).get(data["card_id"])
        if current_bidder is not None:
            bid = data["current_bid"]
            winner = self.session.query(models.GamePlayer).get(current_bidder)
            # Funds were checked at bid time; recheck for safety in case balance
            # changed during the auction (unlikely but possible across turns).
            if self.ledger.player_balance(current_bidder) < bid:
                # Winner can't pay — return to bank.
                self._resolve(pending)
                return "no_bids"
            self.ledger.pay_bank(winner, bid, "card_purchase", pending.turn_id,
                                 notes=f"Won {card.title} at auction (${bid})")
            CardService(self.session, self.game_id).retain_card(
                winner, card, pending.turn_id
            )
            self._resolve(pending)
            return "awarded"

        # No bids at all → card returned to the Bank (stays in the deck).
        self._resolve(pending)
        return "no_bids"

    # ── Tucker Bag Card ─────────────────────────────────────────────────

    def tucker_bag_acknowledge(self, player_id: int, buy_card: bool = False) -> dict:
        """Player acknowledges a Tucker Bag card and its effects are applied."""
        pending = self._validate_pending("tucker_bag_drawn", player_id)
        data = json.loads(pending.action_data)

        player = self.session.query(models.GamePlayer).get(player_id)
        card = self.session.query(models.Card).get(data["card_id"])

        if not card:
            self._resolve(pending)
            return {"status": "acknowledged", "error": "Card not found"}

        # Apply card effect
        card_service = CardService(self.session, self.game_id)
        result = card_service.apply_effect(player, card, pending.turn_id)

        # Handle retainable cards
        offer_to_others = False
        if card.is_retainable:
            params = json.loads(card.effect_params) if card.effect_params else {}
            purchase_price = params.get("purchase_price", 0)
            if purchase_price > 0:
                # Purchasable retainable (e.g., Fire Fighting Equipment) — only on opt-in
                if buy_card:
                    balance = self.ledger.player_balance(player_id)
                    if balance >= purchase_price:
                        self.ledger.pay_bank(player, purchase_price, "card_purchase", pending.turn_id,
                                            notes=f"Purchased {card.title}")
                        card_service.retain_card(player, card, pending.turn_id)
                        result["card_purchased"] = True
                else:
                    # Refused — Fire Fighting Equipment must be offered to other players.
                    if card.effect_code == "FIRE_FIGHTING_EQUIPMENT":
                        offer_to_others = True
            else:
                # Free retainable card — always retained
                card_service.retain_card(player, card, pending.turn_id)
                result["card_retained"] = True

        self._resolve(pending)

        # Refused FFE → with one other player, fixed-price offer at $350;
        # with 2+ others, open a highest-bid auction.
        if offer_to_others:
            others = (
                self.session.query(models.GamePlayer)
                .filter(models.GamePlayer.game_id == self.game_id,
                        models.GamePlayer.is_active.is_(True),
                        models.GamePlayer.game_player_id != player.game_player_id)
                .order_by(models.GamePlayer.turn_order)
                .all()
            )
            params = json.loads(card.effect_params) if card.effect_params else {}
            offer_price = params.get("purchase_price", 350)
            if len(others) == 1:
                self._create_pending_action_raw(pending.turn_id, others[0],
                                                "fire_fighting_offer", {
                    "card_id": card.card_id,
                    "card_title": card.title,
                    "card_body": card.body_text,
                    "price": offer_price,
                    "remaining_queue": [],
                })
            elif len(others) >= 2:
                self._create_fire_fighting_auction(pending.turn_id, card, others, offer_price)

        # Reconciliation popups for "protection or take damage" Tucker Bag
        # cards. Each follow-up pending carries effect_code so the frontend
        # can render the right wording. Grass Fire keeps the board-anchored
        # overlay style when unprotected (stock_card_used set); the modal
        # only renders for its protected case.
        damage_card_codes = {
            "LUCERNE_FLEA", "FIRE_DAMAGE", "WORM_INFESTATION",
            "GRASS_FIRE", "BLOWFLY_WAVE",
        }
        if card.effect_code in damage_card_codes:
            self._create_pending_action_raw(pending.turn_id, player, "tucker_bag_result", {
                "card_title": card.title,
                "effect_code": card.effect_code,
                "protected": result.get("protected", False),
                "protection_card": result.get("protection_card"),
                # Lucerne / Worm / Grass Fire damage fields
                "total_pens_before": result.get("total_pens_before"),
                "fraction_text": result.get("fraction_text"),
                "pens_sold": result.get("pens_sold", 0),
                "sell_price_per_pen": result.get("sell_price_per_pen"),
                "income": result.get("income", 0),
                "by_type": result.get("by_type"),
                "restock_blocked": result.get("restock_blocked", False),
                # Fire Damage / Grass Fire
                "cost": result.get("cost"),
                "haystack_lost": result.get("haystack_lost", False),
                # Grass Fire (board overlay)
                "stock_card_used": result.get("stock_card_used"),
                # Blowfly Wave
                "wool_reduction_pct": result.get("wool_reduction_pct"),
            })

        # "Special Sheep Sale — move to next Stock Sale" should give the player
        # the buy/sell/pass choice on arrival, same as landing there via dice.
        if card.effect_code == "MOVE_TO_STOCK_SALE" and result.get("moved_to"):
            from app.constants import MAX_PENS_PER_TRANSACTION
            self._create_pending_action_raw(pending.turn_id, player, "stock_sale_decision", {
                "space_name": result["moved_to"],
                "in_drought": bool(player.is_in_drought),
                "total_pens": self.station.get_total_pens(player.game_player_id),
                "empty_pens": self.station.get_empty_pens(player.game_player_id),
                "empty_irrigated_pens": self.station.get_empty_pens_by_type(
                    player.game_player_id, "irrigated"),
                "max_per_transaction": MAX_PENS_PER_TRANSACTION,
                "restock_blocked": bool(player.restock_blocked_until_circuit),
                "restock_block_spaces_remaining": player.restock_block_spaces_remaining or 0,
            })

        return {"status": "acknowledged", "effect": result}

    def _create_pending_action_raw(self, turn_id, player, action_type, data):
        action = models.PendingAction(
            game_id=self.game_id,
            turn_id=turn_id,
            action_type=action_type,
            active_player_id=player.game_player_id,
            action_data=json.dumps(data),
        )
        self.session.add(action)
        self.session.flush()

    # ── Expense Payment ─────────────────────────────────────────────────

    def expense_acknowledge(self, player_id: int, buy_card: bool = False,
                            option: str = None) -> dict:
        """Player acknowledges expense payment.
        For an alternative-payment expense (Drench Sheep for Worms): `option`
        must be 'basic' or 'enhanced'.
        Otherwise, buy_card=True purchases the optional immunity card."""
        pending = self._validate_pending("expense_payment", player_id)
        data = json.loads(pending.action_data)

        # Alternative-payment flow (Drench Sheep for Worms)
        if data.get("alternative_payment"):
            if option not in ("basic", "enhanced"):
                raise ValueError("Must choose 'basic' or 'enhanced' option")
            player = self.session.query(models.GamePlayer).get(player_id)
            opt_data = data["enhanced_option" if option == "enhanced" else "basic_option"]
            cost = opt_data["cost"]
            balance = self.ledger.player_balance(player_id)
            if balance < cost:
                raise ValueError(f"Insufficient funds: need ${cost}, have ${balance}")
            self.ledger.pay_bank(player, cost, "expense", pending.turn_id,
                                 notes=f"{data['space_name']} ({opt_data['label']})")
            if option == "enhanced":
                # Grant Worm Control Programme card and +20% next sell modifier.
                player.next_sell_price_modifier = (player.next_sell_price_modifier or 0) + 20
                self.session.flush()
                from app.services.card_service import CardService
                card_service = CardService(self.session, self.game_id)
                card = self.session.query(models.Card).filter_by(title=opt_data["card_name"]).first()
                if card:
                    card_service.retain_card(player, card, pending.turn_id)
            self._resolve(pending)
            return {"status": "acknowledged", "option": option, "cost": cost}

        result = {"status": "acknowledged", "total_cost": data.get("total_cost", 0)}

        if buy_card and data.get("card_option"):
            card_option = data["card_option"]
            card_name = card_option["card_name"]
            card_cost = card_option["card_cost"]

            player = self.session.query(models.GamePlayer).get(player_id)
            balance = self.ledger.player_balance(player_id)

            if balance < card_cost:
                raise ValueError(f"Insufficient funds: need ${card_cost}, have ${balance}")

            # Find the card in the cards table
            card = self.session.query(models.Card).filter_by(title=card_name).first()
            if not card:
                raise ValueError(f"Card '{card_name}' not found")

            # Charge the player
            self.ledger.pay_bank(player, card_cost, "card_purchase", pending.turn_id,
                                notes=f"Purchased {card_name}")

            # Create a CardDraw record to mark card as retained
            from sqlalchemy import func as sa_func
            draw_order = (
                self.session.query(sa_func.coalesce(sa_func.max(models.CardDraw.draw_order), 0))
                .filter_by(game_id=self.game_id)
                .scalar()
            ) + 1

            draw = models.CardDraw(
                game_id=self.game_id,
                turn_id=pending.turn_id,
                deck_type="expense_immunity",
                card_id=card.card_id,
                draw_order=draw_order,
                kept_by_player_id=player_id,
            )
            self.session.add(draw)
            self.session.flush()

            result["card_purchased"] = card_name
            result["card_cost"] = card_cost

        self._resolve(pending)
        return result

    # ── Generic Acknowledgements ────────────────────────────────────────

    def acknowledge(self, player_id: int) -> dict:
        """Generic acknowledge for informational pending actions."""
        pending = self.get_pending_action()
        if not pending:
            raise ValueError("No pending action")
        if pending.active_player_id != player_id:
            raise ValueError("Not this player's decision")

        data = json.loads(pending.action_data) if pending.action_data else {}
        self._resolve(pending)
        return {"status": "acknowledged", "action_type": pending.action_type, "data": data}

    # ── Helpers ──────────────────────────────────────────────────────────

    def _validate_pending(self, expected_type: str, player_id: int) -> models.PendingAction:
        pending = self.get_pending_action()
        if not pending:
            raise ValueError("No pending action")
        if pending.action_type != expected_type:
            raise ValueError(f"Expected {expected_type}, got {pending.action_type}")
        if pending.active_player_id != player_id:
            raise ValueError("Not this player's decision")
        return pending

    def _resolve(self, pending: models.PendingAction):
        pending.resolved_at = func.now()
        self.session.flush()

    def _calculate_sell_income(self, player_id: int, pens: int,
                               stock_card: models.StockCard, modifier_pct: int,
                               in_drought: bool = False) -> dict:
        """Calculate total income from selling pens, using paddock-type pricing.
        Returns {"total": int, "tiers": [(paddock_type, pens), ...]} so the caller
        can remove sheep in the same tier order. During drought, Natural and
        Improved are halved (rule: stock sold from Natural/Improved during a
        drought is at half the normal price). Irrigated remains at full price."""
        paddocks = self.station.get_paddocks(player_id)
        natural_pens = sum(p.sheep_pens for p in paddocks if p.paddock_type == "natural")
        improved_pens = sum(p.sheep_pens for p in paddocks if p.paddock_type == "improved")
        irrigated_pens = sum(p.sheep_pens for p in paddocks if p.paddock_type == "irrigated")

        natural_price = stock_card.sell_price_natural
        improved_price = stock_card.sell_price_improved_irrigated
        irrigated_price = stock_card.sell_price_improved_irrigated

        if modifier_pct:
            natural_price = int(natural_price * (100 + modifier_pct) / 100)
            improved_price = int(improved_price * (100 + modifier_pct) / 100)
            irrigated_price = int(irrigated_price * (100 + modifier_pct) / 100)

        if in_drought:
            natural_price = natural_price // 2
            improved_price = improved_price // 2

        # Sell order: natural → improved → irrigated (consume cheapest first;
        # in drought this also drains the discounted tiers first as you'd expect).
        remaining = pens
        from_natural = min(remaining, natural_pens); remaining -= from_natural
        from_improved = min(remaining, improved_pens); remaining -= from_improved
        from_irrigated = min(remaining, irrigated_pens); remaining -= from_irrigated

        total = (from_natural * natural_price
                 + from_improved * improved_price
                 + from_irrigated * irrigated_price)

        return {
            "total": total,
            "tiers": [
                ("natural", from_natural),
                ("improved", from_improved),
                ("irrigated", from_irrigated),
            ],
        }
