# app/services/space_resolver.py
import json
from typing import Optional, TYPE_CHECKING
from sqlalchemy.orm import Session
from app import models
from app.services.ledger_service import LedgerService
from app.services.station_service import StationService
from app.services.stock_sale_service import StockSaleService
from app.services.drought_service import DroughtService

if TYPE_CHECKING:
    from .card_service import CardService


class SpaceResolver:
    def __init__(self, session: Session, game_id: int, card_service: Optional["CardService"] = None):
        self.session = session
        self.game_id = game_id
        self.ledger = LedgerService(session, game_id)
        self.station = StationService(session, game_id)
        self.stock_sale = StockSaleService(session, game_id)
        self.drought = DroughtService(session, game_id)
        self.card_service = card_service
        # Set by TurnManager before each resolve(): whether the player was
        # in drought at the start of this turn, before track_movement may
        # have broken it. Used so an anniversary landing on a Local Drought
        # space extends rather than re-charges. See _handle_local_drought.
        self.was_in_drought_at_turn_start = False

    def resolve(self, player: models.GamePlayer, space: models.Space, turn, passed_start: bool):
        won_on_pass = False
        # Handle wool cheque when passing Wool Sale (without landing on it)
        if passed_start and space.board_index != 0:
            cheque = self._pay_wool_cheque(player, turn)
            # Show breakdown via a pending action created BEFORE the destination
            # space handler runs, so it's surfaced first (oldest pending wins).
            self._create_pending_action(turn, player, "wool_cheque_paid", {
                "space_name": "Start/Wool Sale",
                "trigger": "passed",
                **cheque,
            })
            won_on_pass = self.station.declare_winner_if_eligible(
                player.game_player_id, turn.turn_id
            )

        # Skip further space resolution if the player has already won.
        if not won_on_pass:
            handler = getattr(self, f"_handle_{space.space_type}", self._handle_default)
            handler(player, space, turn, passed_start)

            # Haymaking season: every space tagged "Haymaking" offers a haystack
            # purchase to any player who doesn't already own one.
            self._maybe_offer_haystack(player, space, turn)

    def _maybe_offer_haystack(self, player, space, turn):
        if space.season != "Haymaking":
            return
        # Offer only haystack types the player can use and doesn't already hold.
        offers = self.station.useful_haystack_offers(player)
        if not offers:
            return

        # Attach to whatever pending action this turn already has; otherwise
        # create a standalone offer so the modal can present it.
        pending = (
            self.session.query(models.PendingAction)
            .filter_by(
                game_id=self.game_id,
                turn_id=turn.turn_id,
                active_player_id=player.game_player_id,
                resolved_at=None,
            )
            .order_by(models.PendingAction.pending_action_id.desc())
            .first()
        )
        if pending:
            data = json.loads(pending.action_data) if pending.action_data else {}
            data["haystack_offers"] = offers
            data["haystack_drought_premium"] = bool(player.is_in_drought)
            pending.action_data = json.dumps(data)
            self.session.flush()
        else:
            self._create_pending_action(turn, player, "haystack_offer", {
                "space_name": space.name,
                "haystack_offers": offers,
                "haystack_drought_premium": bool(player.is_in_drought),
            })

    # ── Wool Sale (Start) ────────────────────────────────────────────────

    def _handle_wool_sale(self, player, space, turn, passed_start):
        cheque = self._pay_wool_cheque(player, turn)
        self._create_pending_action(turn, player, "wool_cheque_paid", {
            "space_name": space.name,
            "trigger": "landed",
            **cheque,
        })
        self.station.declare_winner_if_eligible(player.game_player_id, turn.turn_id)

    def _pay_wool_cheque(self, player, turn):
        """Pay wool cheque + any mortgage interest. Returns breakdown for UI."""
        from app.constants import WOOL_CHEQUE_PER_PEN, STUD_RAM_WOOL_BONUS_PER_PEN
        cheque = self.station.calculate_wool_cheque(player.game_player_id)
        if cheque["total"] > 0:
            notes = f"Wool Cheque ({cheque['total_pens']} pens, {cheque['stud_rams']} ram)"
            self.ledger.record_wool_cheque(player, cheque["total"], turn.turn_id, notes=notes)
        # Reset single-use card effects after use
        if player.wool_cheque_bonus:
            player.wool_cheque_bonus = 0
        if player.wool_cheque_blowfly_pct:
            player.wool_cheque_blowfly_pct = 0
        # Pay mortgage interest
        interest = self.station.calculate_mortgage_interest(player.game_player_id)
        if interest > 0:
            self.ledger.record_mortgage_interest(player, interest, turn.turn_id)
        self.session.flush()
        return {
            **cheque,
            "mortgage_interest": interest,
            "per_pen_rate": WOOL_CHEQUE_PER_PEN,
            "per_pen_per_ram_rate": STUD_RAM_WOOL_BONUS_PER_PEN,
        }

    # ── Stock Sale ───────────────────────────────────────────────────────

    def _handle_stock_sale(self, player, space, turn, passed_start):
        # Rule: the player MUST declare buy/sell/pass and the number of pens
        # BEFORE the Stock Sale card is revealed. We do NOT draw the card here
        # — that happens inside stock_sale_buy / stock_sale_sell, after the
        # player has committed.
        # Worm Infestation: clear the restock block on this Stock Sale landing
        # per the card text ("You can restock when you land on the next
        # Stock Sale.").
        if player.restock_block_until_stock_sale:
            player.restock_blocked_until_circuit = False
            player.restock_block_spaces_remaining = 0
            player.restock_block_scope = None
            player.restock_block_until_stock_sale = False
            player.restock_block_marker_board_index = None
            player.restock_block_source = None
            self.session.flush()
        from app.constants import MAX_PENS_PER_TRANSACTION
        total_pens = self.station.get_total_pens(player.game_player_id)
        empty_pens = self.station.get_empty_pens(player.game_player_id)
        empty_irrigated = self.station.get_empty_pens_by_type(
            player.game_player_id, "irrigated"
        )
        self._create_pending_action(turn, player, "stock_sale_decision", {
            "space_name": space.name,
            "in_drought": bool(player.is_in_drought),
            "total_pens": total_pens,
            "empty_pens": empty_pens,
            "empty_irrigated_pens": empty_irrigated,
            "max_per_transaction": MAX_PENS_PER_TRANSACTION,
            # Bore Dries Up / Tucker Bag (Lucerne Flea / Grass Fire) impose a
            # restock block until the player completes a full circuit (or the
            # halved 22-space variant). UI uses these to disable the Buy button.
            "restock_blocked": bool(player.restock_blocked_until_circuit),
            "restock_block_spaces_remaining": player.restock_block_spaces_remaining or 0,
            "restock_block_scope": player.restock_block_scope,
            "empty_natural_pens": self.station.get_empty_pens_by_type(player.game_player_id, "natural"),
            "empty_improved_pens": self.station.get_empty_pens_by_type(player.game_player_id, "improved"),
            # Per-type pens HELD — so the Sell step can let the player allocate.
            "natural_pens": sum(p.sheep_pens for p in self.station.get_paddocks(player.game_player_id) if p.paddock_type == "natural"),
            "improved_pens": sum(p.sheep_pens for p in self.station.get_paddocks(player.game_player_id) if p.paddock_type == "improved"),
            "irrigated_pens": sum(p.sheep_pens for p in self.station.get_paddocks(player.game_player_id) if p.paddock_type == "irrigated"),
            # Modifier visibility — refreshed by get_pending_action_state on each poll.
            "next_sell_price_modifier": player.next_sell_price_modifier or 0,
            "balance": self.ledger.player_balance(player.game_player_id),
        })

    # ── Tucker Bag ───────────────────────────────────────────────────────

    def _handle_tucker_bag(self, player, space, turn, passed_start):
        if self.card_service:
            card = self.card_service.draw_card(turn.turn_id)
            params = json.loads(card.effect_params) if card.effect_params else {}
            action_data = {
                "card_id": card.card_id,
                "title": card.title,
                "body_text": card.body_text,
                "effect_code": card.effect_code,
                "is_retainable": card.is_retainable,
                # Purchasable retainable (e.g., Fire Fighting Equipment $350) carries a
                # price so the modal can offer Buy / Decline. 0 for free retainables.
                "purchase_price": params.get("purchase_price", 0),
            }

            # Add breakdown for Income Tax Assessment
            if card.effect_code == "INCOME_TAX":
                action_data["tax_breakdown"] = self._calculate_tax_breakdown(
                    player, params)

            self._create_pending_action(turn, player, "tucker_bag_drawn", action_data)

    # ── Stud Ram ─────────────────────────────────────────────────────────

    def _handle_stud_ram(self, player, space, turn, passed_start):
        ram_state = (
            self.session.query(models.StudRamState)
            .filter_by(game_id=self.game_id, space_id=space.space_id)
            .first()
        )
        if not ram_state:
            return

        if ram_state.owner_game_player_id is None and ram_state.is_available:
            # Unowned — offer purchase
            self._create_pending_action(turn, player, "stud_ram_purchase", {
                "space_id": space.space_id,
                "space_name": space.name,
                "purchase_price": space.purchase_price,
                "stud_fee": space.stud_fee,
            })
        elif ram_state.owner_game_player_id and ram_state.owner_game_player_id != player.game_player_id:
            # Owned by another player — pay stud fee
            owner = self.session.query(models.GamePlayer).get(ram_state.owner_game_player_id)
            if space.stud_fee and owner:
                self.ledger.pay_player(player, owner, space.stud_fee, "stud_fee", turn.turn_id,
                                       space_id=space.space_id,
                                       notes=f"Stud fee for {space.name}")
                self._create_pending_action(turn, player, "stud_fee_paid", {
                    "amount": space.stud_fee,
                    "owner_name": owner.player_name,
                    "ram_name": space.name,
                })

    # ── Expense Spaces ───────────────────────────────────────────────────

    def _handle_expense(self, player, space, turn, passed_start):
        total_pens = self.station.get_total_pens(player.game_player_id)

        # Fly Strike Dip / Jet Sheep — landing here clears any pending
        # Blowfly Wave wool-cheque penalty (per the Blowfly card text:
        # "No loss if you land on space marked 'Jet Sheep' before your
        # next Wool Cheque.").
        blowfly_cleared = 0
        if space.board_index == 40 and (player.wool_cheque_blowfly_pct or 0) > 0:
            blowfly_cleared = player.wool_cheque_blowfly_pct
            player.wool_cheque_blowfly_pct = 0
            self.session.flush()

        # Check if player holds the relevant card for immunity
        has_card = False
        if space.relevant_card_name:
            has_card = self._player_has_retained_card(player, space.relevant_card_name)

        # ── Drench Sheep for Worms (two alternative options, NOT auto-pay) ──
        # Rule: (a) pay $10/pen for basic drench, OR
        #       (b) pay $20/pen for proper Worm Control Programme — gain
        #           "Worm Control Programme" card → +20% next sell, card returned.
        if space.board_index == 8 and not has_card:
            # If the player has no sheep, neither option applies — no pending
            # action needed; the player just proceeds.
            if total_pens == 0:
                return
            basic_cost = (space.cost_per_pen or 10) * total_pens
            enhanced_cost = (space.cost_per_pen_with_card or 20) * total_pens
            self._create_pending_action(turn, player, "expense_payment", {
                "space_name": space.name,
                "total_pens": total_pens,
                "has_card": has_card,
                "alternative_payment": True,
                "basic_option": {
                    "label": "Basic drench",
                    "cost": basic_cost,
                    "rate_per_pen": space.cost_per_pen or 10,
                },
                "enhanced_option": {
                    "label": "Worm Control Programme (+20% next sell)",
                    "cost": enhanced_cost,
                    "rate_per_pen": space.cost_per_pen_with_card or 20,
                    "card_name": space.relevant_card_name,
                },
            })
            return

        # Standard expense path (immune via card → pay nothing; otherwise pay listed cost).
        if has_card:
            cost_per_pen = 0
            cost_flat = 0
        else:
            cost_per_pen = space.cost_per_pen or 0
            cost_flat = space.cost_flat or 0

        total_cost = (cost_per_pen * total_pens) + cost_flat

        if total_cost > 0:
            self.ledger.pay_bank(player, total_cost, "expense", turn.turn_id,
                                 space_id=space.space_id,
                                 notes=space.name)

        # "Spray for Weeds and Insects" grants 20% sell bonus at next stock sale
        # and automatically grants the immunity card
        if space.board_index == 21 and not has_card:
            player.next_sell_price_modifier = 20
            self._grant_expense_card(player, space.relevant_card_name, turn)
            self.session.flush()

        # "Pay Cost of Fertilising Pasture" grants sell bonus too
        # and automatically grants the immunity card
        if space.board_index == 37 and not has_card:
            player.next_sell_price_modifier = 20
            self._grant_expense_card(player, space.relevant_card_name, turn)
            self.session.flush()

        action_data = {
            "space_name": space.name,
            "total_cost": total_cost,
            "cost_per_pen": cost_per_pen,
            "cost_flat": cost_flat,
            "total_pens": total_pens,
            "has_card": has_card,
        }

        # Notify about card grant for spaces 21/37
        if space.board_index in (21, 37) and not has_card:
            action_data["card_granted"] = space.relevant_card_name

        # Notify the popup when Fly Strike Dip cleared a Blowfly Wave penalty.
        if blowfly_cleared:
            action_data["blowfly_cleared_pct"] = blowfly_cleared

        self._create_pending_action(turn, player, "expense_payment", action_data)

    # ── Visiting Town ────────────────────────────────────────────────────

    def _handle_visiting_town(self, player, space, turn, passed_start):
        player.visiting_town_turns = 2
        self.session.flush()
        self._create_pending_action(turn, player, "visiting_town", {
            "turns_to_miss": 2,
        })

    # ── Local Drought ────────────────────────────────────────────────────

    def _handle_local_drought(self, player, space, turn, passed_start):
        from app.constants import DROUGHT_SELL_PRICE_NO_HAYSTACK

        # Rule: "Stock on Irrigated Pasture are not affected by Local Drought."
        # If the player owns NO Natural or Improved paddocks, the drought has
        # no effect on them — no marker, no sale, no restrictions.
        non_irrigated_paddocks = [
            p for p in self.station.get_paddocks(player.game_player_id)
            if p.paddock_type in ("natural", "improved")
        ]
        if not non_irrigated_paddocks:
            self._create_pending_action(turn, player, "drought_effect", {
                "pens_sold": 0,
                "income": 0,
                "drought_spaces": 0,
                "had_haystack": bool(player.haystack_pasture),
                "extended": False,
                "no_effect": True,
                "reason": "All paddocks are Irrigated — drought has no effect.",
            })
            return

        # Treat an anniversary landing as a continuation: if the player was in
        # drought at the start of this turn, track_movement may have just
        # broken it as the circuit completed on this very space. Either way it
        # extends — no second half-stock sale.
        already_in_drought = player.is_in_drought or self.was_in_drought_at_turn_start
        pens_sold = 0
        total_income = 0
        # Local Drought hits Natural/Improved stock, so the PASTURE haystack
        # offsets it (the irrigated haystack is for Bore Dries Up).
        had_haystack = bool(player.haystack_pasture)
        stock_card_drawn = None
        by_type = {"natural": 0, "improved": 0, "irrigated": 0}

        if not already_in_drought:
            # Sell half non-irrigated stock. If already in drought, extending the
            # period neither sells more stock nor forfeits a haystack.
            breakdown = self.station.sell_half_stock(
                player.game_player_id, exclude_irrigated=True, return_breakdown=True
            )
            pens_sold = breakdown["total"]
            by_type = breakdown["by_type"]

            if pens_sold > 0:
                if had_haystack:
                    # Rule: with a haystack, the player turns up the next Stock
                    # Sale card to settle the per-pen sell price.
                    stock_card_drawn = self.stock_sale.draw_stock_card(turn.turn_id)
                    total_income = (
                        by_type["natural"] * stock_card_drawn.sell_price_natural
                        + by_type["improved"] * stock_card_drawn.sell_price_improved_irrigated
                        + by_type["irrigated"] * stock_card_drawn.sell_price_improved_irrigated
                    )
                    notes = (f"Drought: sold {pens_sold} pens at Stock Sale prices "
                             f"(pasture haystack consumed)")
                    # Pasture haystack is "used" when it offsets a Local Drought.
                    player.haystack_pasture = False
                    self.session.flush()
                else:
                    total_income = pens_sold * DROUGHT_SELL_PRICE_NO_HAYSTACK
                    notes = (f"Drought: sold {pens_sold} pens at "
                             f"${DROUGHT_SELL_PRICE_NO_HAYSTACK}/pen (no haystack)")

                self.ledger.receive_from_bank(
                    player, total_income, "drought_sale", turn.turn_id, notes=notes
                )
            # else: no Natural/Improved stock to sell → haystack preserved per rule

        self.drought.apply_drought(player, space.board_index)

        self._create_pending_action(turn, player, "drought_effect", {
            "pens_sold": pens_sold,
            "income": total_income,
            "drought_spaces": player.drought_spaces_remaining,
            "had_haystack": had_haystack,
            "extended": already_in_drought,
            "by_type": by_type,
            "no_haystack_price_per_pen": DROUGHT_SELL_PRICE_NO_HAYSTACK,
            "stock_card_used": (
                {
                    "buy_price_per_pen": stock_card_drawn.buy_price_per_pen,
                    "sell_price_natural": stock_card_drawn.sell_price_natural,
                    "sell_price_improved_irrigated":
                        stock_card_drawn.sell_price_improved_irrigated,
                } if stock_card_drawn else None
            ),
        })

    # ── Local Rain ───────────────────────────────────────────────────────

    def _handle_local_rain(self, player, space, turn, passed_start):
        was_in_drought = player.is_in_drought
        if was_in_drought:
            self.drought.break_drought(player, source="local_rain")
        self._create_pending_action(turn, player, "local_rain", {
            "drought_broken": was_in_drought,
        })

    # ── Bore Dries Up ────────────────────────────────────────────────────

    def _handle_bore_dries_up(self, player, space, turn, passed_start):
        from app.constants import (BORE_DRIES_UP_PRICE_NO_HAYSTACK,
                                   BORE_DRIES_UP_PRICE_WITH_HAYSTACK,
                                   BOARD_SIZE)
        affected = self.drought.apply_bore_dries_up(player)
        pens_sold = 0
        total_income = 0
        # Bore Dries Up hits Irrigated stock, so the IRRIGATED haystack offsets
        # it (the pasture haystack is for Local Drought).
        had_haystack = bool(player.haystack_irrigated)
        price_per_pen = 0
        halved = False

        if affected:
            # Rule: sell half stock from IRRIGATED pasture (rounded up).
            pens_sold = self.station.sell_half_stock(
                player.game_player_id, irrigated_only=True
            )
            if pens_sold > 0:
                if had_haystack:
                    price_per_pen = BORE_DRIES_UP_PRICE_WITH_HAYSTACK
                    notes = (f"Bore dried up: sold {pens_sold} irrigated pens "
                             f"at ${price_per_pen}/pen (irrigated haystack consumed)")
                    # Irrigated haystack consumed when it offsets the bore.
                    player.haystack_irrigated = False
                else:
                    price_per_pen = BORE_DRIES_UP_PRICE_NO_HAYSTACK
                    notes = (f"Bore dried up: sold {pens_sold} irrigated pens "
                             f"at ${price_per_pen}/pen")
                total_income = pens_sold * price_per_pen
                self.ledger.receive_from_bank(player, total_income, "bore_sale",
                                              turn.turn_id, notes=notes)

            # Restock-block duration: full circuit, OR halved (22 spaces) if the
            # Sustainable Water Management Tucker Bag effect is queued. The
            # halved flag is consumed here regardless of Local Drought.
            # Scope = 'irrigated' because Bore Dries Up only restricts
            # restocking onto Irrigated pasture; Natural/Improved are free.
            player.restock_blocked_until_circuit = True
            player.restock_block_scope = 'irrigated'
            # Board marker: pin where the bore dried up so the circuit is
            # visible (cleared when the block lifts — see TurnManager).
            player.restock_block_marker_board_index = space.board_index
            player.restock_block_source = 'bore_dries_up'
            if player.next_drought_halved:
                player.restock_block_spaces_remaining = BOARD_SIZE // 2
                player.next_drought_halved = False
                halved = True
            else:
                player.restock_block_spaces_remaining = BOARD_SIZE
            self.session.flush()

        self._create_pending_action(turn, player, "bore_dries_up_effect", {
            "space_name": space.name,
            "affected": affected,
            "pens_sold": pens_sold,
            "income": total_income,
            "price_per_pen": price_per_pen,
            "had_haystack": had_haystack,
            "halved_duration": halved,
            "spaces_blocked": player.restock_block_spaces_remaining if affected else 0,
            "no_effect": not affected,
            "reason": (
                "You have no Irrigated pasture — Bore Dries Up has no effect."
                if not affected else None
            ),
        })

    # ── Flood Damage ─────────────────────────────────────────────────────

    def _handle_flood_damage(self, player, space, turn, passed_start):
        from app.constants import FLOOD_DAMAGE_REPAIR_COST
        cost = FLOOD_DAMAGE_REPAIR_COST
        self.ledger.pay_bank(player, cost, "flood_damage", turn.turn_id,
                             notes=f"Flood damage repairs: ${cost}")

        self._create_pending_action(turn, player, "flood_effect", {
            "total_cost": cost,
        })

    # ── Stud Ram Dies ────────────────────────────────────────────────────

    def _handle_stud_ram_dies(self, player, space, turn, passed_start):
        # Rule: ONLY the landing player is affected. If they own one or more
        # stud rams, their ram with the highest stud fee is returned to the bank.
        my_rams = (
            self.session.query(models.StudRamState)
            .filter_by(game_id=self.game_id, owner_game_player_id=player.game_player_id)
            .all()
        )
        if not my_rams:
            self._create_pending_action(turn, player, "stud_ram_dies", {"affected": False})
            return

        def fee_of(ram):
            sp = self.session.query(models.Space).get(ram.space_id)
            return sp.stud_fee or 0 if sp else 0

        highest_fee_ram = max(my_rams, key=fee_of)
        affected_space = self.session.query(models.Space).get(highest_fee_ram.space_id)

        # Stud Ram Insurance card (retainable) refunds $500 if held.
        has_insurance = self._player_has_retained_card(player, "Stud Ram Insurance")
        if has_insurance:
            self.ledger.receive_from_bank(player, 500, "stud_ram_insurance", turn.turn_id,
                                          notes="Stud Ram Insurance refund")
            self._consume_retained_card(player, "Stud Ram Insurance")

        # Return ram to bank — becomes available for repurchase.
        highest_fee_ram.owner_game_player_id = None
        highest_fee_ram.is_available = True
        self.session.flush()

        self._create_pending_action(turn, player, "stud_ram_dies", {
            "affected": True,
            "owner_name": player.player_name,
            "ram_name": affected_space.name if affected_space else None,
            "had_insurance": has_insurance,
        })

    # ── Default ──────────────────────────────────────────────────────────

    def _handle_default(self, player, space, turn, passed_start):
        pass

    # ── Helpers ──────────────────────────────────────────────────────────

    def _create_pending_action(self, turn, player, action_type, data):
        action = models.PendingAction(
            game_id=self.game_id,
            turn_id=turn.turn_id,
            action_type=action_type,
            active_player_id=player.game_player_id,
            action_data=json.dumps(data),
        )
        self.session.add(action)
        self.session.flush()
        return action

    def _player_has_retained_card(self, player, card_name: str) -> bool:
        if not player:
            return False
        card_draw = (
            self.session.query(models.CardDraw)
            .join(models.Card)
            .filter(
                models.CardDraw.game_id == self.game_id,
                models.CardDraw.kept_by_player_id == player.game_player_id,
                models.Card.title == card_name,
                models.CardDraw.discarded_at.is_(None),
            )
            .first()
        )
        return card_draw is not None

    def _calculate_tax_breakdown(self, player, params):
        """Calculate Income Tax Assessment breakdown for display."""
        pid = player.game_player_id
        paddocks = self.station.get_paddocks(pid)
        balance = self.ledger.player_balance(pid)

        natural_count = sum(1 for p in paddocks if p.paddock_type == "natural")
        improved_count = sum(1 for p in paddocks if p.paddock_type == "improved")
        irrigated_count = sum(1 for p in paddocks if p.paddock_type == "irrigated")
        total_pens = sum(p.sheep_pens for p in paddocks)
        cash_thousands = (balance + 500) // 1000  # rounded to nearest $1000

        lines = []
        if natural_count > 0:
            amount = natural_count * params["per_natural_paddock"]
            lines.append({
                "label": f"{natural_count} natural paddock{'s' if natural_count != 1 else ''}",
                "rate": params["per_natural_paddock"],
                "amount": amount,
            })
        if improved_count > 0:
            amount = improved_count * params["per_improved_paddock"]
            lines.append({
                "label": f"{improved_count} improved paddock{'s' if improved_count != 1 else ''}",
                "rate": params["per_improved_paddock"],
                "amount": amount,
            })
        if irrigated_count > 0:
            amount = irrigated_count * params["per_irrigated_paddock"]
            lines.append({
                "label": f"{irrigated_count} irrigated paddock{'s' if irrigated_count != 1 else ''}",
                "rate": params["per_irrigated_paddock"],
                "amount": amount,
            })
        if total_pens > 0:
            amount = total_pens * params["per_pen"]
            lines.append({
                "label": f"{total_pens} pen{'s' if total_pens != 1 else ''} of sheep",
                "rate": params["per_pen"],
                "amount": amount,
            })
        if cash_thousands > 0:
            amount = cash_thousands * params["per_1000_cash"]
            lines.append({
                "label": f"${cash_thousands * 1000:,} cash",
                "rate": params["per_1000_cash"],
                "rate_label": f"@ ${params['per_1000_cash']} per $1,000",
                "amount": amount,
            })

        total = sum(line["amount"] for line in lines)
        return {"lines": lines, "total": total}

    def _grant_expense_card(self, player, card_name: str, turn):
        """Grant an expense immunity card to a player (e.g. after paying at spaces 21/37)."""
        if not card_name:
            return
        # Check if player already has this card
        if self._player_has_retained_card(player, card_name):
            return
        card = self.session.query(models.Card).filter_by(title=card_name).first()
        if not card:
            return
        from sqlalchemy import func as sa_func
        draw_order = (
            self.session.query(sa_func.coalesce(sa_func.max(models.CardDraw.draw_order), 0))
            .filter_by(game_id=self.game_id)
            .scalar()
        ) + 1
        draw = models.CardDraw(
            game_id=self.game_id,
            turn_id=turn.turn_id,
            deck_type="expense_immunity",
            card_id=card.card_id,
            draw_order=draw_order,
            kept_by_player_id=player.game_player_id,
        )
        self.session.add(draw)
        self.session.flush()

    def _consume_retained_card(self, player, card_name: str):
        card_draw = (
            self.session.query(models.CardDraw)
            .join(models.Card)
            .filter(
                models.CardDraw.game_id == self.game_id,
                models.CardDraw.kept_by_player_id == player.game_player_id,
                models.Card.title == card_name,
                models.CardDraw.discarded_at.is_(None),
            )
            .first()
        )
        if card_draw:
            from datetime import datetime, timezone
            card_draw.kept_by_player_id = None
            card_draw.discarded_at = datetime.now(timezone.utc)
            self.session.flush()
