# app/services/card_service.py
import json
import random
from typing import Optional, TYPE_CHECKING
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func

from app import models
from app.services.ledger_service import LedgerService
from app.services.station_service import StationService
from app.services.drought_service import DroughtService
from app.services.stock_sale_service import StockSaleService

if TYPE_CHECKING:
    from .space_resolver import SpaceResolver


class CardService:
    def __init__(self, session: Session, game_id: int, space_resolver: Optional["SpaceResolver"] = None):
        self.session = session
        self.game_id = game_id
        self.space_resolver = space_resolver
        self.ledger = LedgerService(session, game_id)
        self.station = StationService(session, game_id)
        self.drought = DroughtService(session, game_id)
        self.stock_sale = StockSaleService(session, game_id)

    def draw_card(self, turn_id: int) -> models.Card:
        """Draw a Tucker Bag card.

        Rule: the FIRST Tucker Bag draw of each game is always Fire Fighting
        Equipment. Subsequent draws are uniformly random from the deck, with
        one-time cards (cards.one_time = TRUE) excluded once they've been drawn."""
        # Has any Tucker Bag card been drawn yet this game?
        prior_count = (
            self.session.query(func.count(models.CardDraw.card_draw_id))
            .filter_by(game_id=self.game_id, deck_type="tucker_bag")
            .scalar()
        )

        if prior_count == 0:
            # First Tucker Bag draw of the game — force Fire Fighting Equipment.
            ffe = (
                self.session.query(models.Card)
                .filter_by(deck_type="tucker_bag", effect_code="FIRE_FIGHTING_EQUIPMENT")
                .first()
            )
            if ffe is None:
                # Fallback to random pool if FFE is missing from the deck for some reason.
                ffe = (
                    self.session.query(models.Card)
                    .filter_by(deck_type="tucker_bag")
                    .first()
                )
            card = ffe
        else:
            # Card IDs of one-time cards already drawn this game.
            already_drawn_one_time = {
                cid for (cid,) in self.session.query(models.CardDraw.card_id)
                    .join(models.Card, models.Card.card_id == models.CardDraw.card_id)
                    .filter(models.CardDraw.game_id == self.game_id,
                            models.Card.one_time.is_(True))
                    .distinct()
                    .all()
            }
            q = self.session.query(models.Card).filter_by(deck_type="tucker_bag")
            if already_drawn_one_time:
                q = q.filter(~models.Card.card_id.in_(already_drawn_one_time))
            all_cards = q.all()
            if not all_cards:
                raise RuntimeError("No Tucker Bag cards available to draw")
            card = random.choice(all_cards)

        draw_order = (
            self.session.query(func.coalesce(func.max(models.CardDraw.draw_order), 0))
            .filter_by(game_id=self.game_id)
            .scalar()
        ) + 1

        draw = models.CardDraw(
            game_id=self.game_id,
            turn_id=turn_id,
            deck_type="tucker_bag",
            card_id=card.card_id,
            draw_order=draw_order,
        )
        self.session.add(draw)
        self.session.flush()
        return card

    def apply_effect(self, player: models.GamePlayer, card: models.Card, turn_id: int) -> dict:
        """Apply a Tucker Bag card effect. Returns result dict."""
        params = json.loads(card.effect_params) if card.effect_params else {}
        handler = getattr(self, f"_effect_{card.effect_code.lower()}", None)
        if handler:
            return handler(player, params, turn_id)
        return {"message": f"Unknown effect: {card.effect_code}"}

    def retain_card(self, player: models.GamePlayer, card: models.Card, turn_id: int):
        """Mark a retainable card as kept by the player."""
        draw = (
            self.session.query(models.CardDraw)
            .filter_by(
                game_id=self.game_id,
                turn_id=turn_id,
                card_id=card.card_id,
            )
            .order_by(models.CardDraw.draw_order.desc())
            .first()
        )
        if draw:
            draw.kept_by_player_id = player.game_player_id
            self.session.flush()

    # ── Effect Handlers ─────────────────────────────────────────────────

    def _effect_collect(self, player, params, turn_id):
        amount = params["amount"]
        self.ledger.receive_from_bank(player, amount, "card_collect", turn_id)
        return {"collected": amount}

    def _effect_fire_damage(self, player, params, turn_id):
        cost = params["cost"]
        protection = params.get("protection_card")
        has_protection = self._has_retained_card(player, protection) if protection else False

        if has_protection:
            return {"protected": True, "card": protection}

        self.ledger.pay_bank(player, cost, "fire_damage", turn_id)

        if player.has_haystack:
            player.has_haystack = False
            player.haystack_used = False
            self.session.flush()
            return {"cost": cost, "haystack_lost": True}

        return {"cost": cost, "haystack_lost": False}

    def _effect_income_tax(self, player, params, turn_id):
        pid = player.game_player_id
        paddocks = self.station.get_paddocks(pid)
        balance = self.ledger.get_balance(pid)

        natural_count = sum(1 for p in paddocks if p.paddock_type == "natural")
        improved_count = sum(1 for p in paddocks if p.paddock_type == "improved")
        irrigated_count = sum(1 for p in paddocks if p.paddock_type == "irrigated")
        total_pens = sum(p.sheep_pens for p in paddocks)
        cash_thousands = (balance + 500) // 1000  # rounded to nearest $1000

        total_tax = (
            natural_count * params["per_natural_paddock"]
            + improved_count * params["per_improved_paddock"]
            + irrigated_count * params["per_irrigated_paddock"]
            + total_pens * params["per_pen"]
            + cash_thousands * params["per_1000_cash"]
        )

        if total_tax > 0:
            self.ledger.pay_bank(player, total_tax, "income_tax", turn_id)

        return {"total_tax": total_tax}

    def _effect_move_to_wool_sale(self, player, params, turn_id):
        from app.constants import WOOL_CHEQUE_PER_PEN, STUD_RAM_WOOL_BONUS_PER_PEN
        if params.get("breaks_drought") and player.is_in_drought:
            self.drought.break_drought(player, source="card")
        # Move to Wool Sale (space 0)
        player.current_space_id = 0
        self.session.flush()

        # Pay wool cheque
        cheque = self.station.calculate_wool_cheque(player.game_player_id)
        wool_cheque_amount = cheque["total"]
        if wool_cheque_amount > 0:
            notes = f"Wool Cheque ({cheque['total_pens']} pens, {cheque['stud_rams']} ram)"
            self.ledger.record_wool_cheque(player, wool_cheque_amount, turn_id, notes=notes)
        # Reset card bonuses after use
        if player.wool_cheque_bonus > 0:
            player.wool_cheque_bonus = 0
        # Pay mortgage interest
        interest = self.station.calculate_mortgage_interest(player.game_player_id)
        if interest > 0:
            self.ledger.record_mortgage_interest(player, interest, turn_id)
        self.session.flush()

        # Show the cheque breakdown to the player (popup acknowledged via
        # /decisions/acknowledge). The previous pending action — the Tucker Bag
        # draw that triggered this effect — is resolved by the caller right
        # after apply_effect returns, so this new pending becomes the active
        # one on the next poll.
        self.session.add(models.PendingAction(
            game_id=self.game_id,
            turn_id=turn_id,
            action_type="wool_cheque_paid",
            active_player_id=player.game_player_id,
            action_data=json.dumps({
                "space_name": "Start/Wool Sale",
                "trigger": "card",
                **cheque,
                "mortgage_interest": interest,
                "per_pen_rate": WOOL_CHEQUE_PER_PEN,
                "per_pen_per_ram_rate": STUD_RAM_WOOL_BONUS_PER_PEN,
            }),
        ))
        self.session.flush()

        return {
            "moved_to": "Wool Sale",
            "drought_broken": params.get("breaks_drought", False),
            "wool_cheque": wool_cheque_amount,
            "mortgage_interest": interest,
        }

    def _effect_lucerne_flea(self, player, params, turn_id):
        protection = params.get("protection_card")
        if protection and self._has_retained_card(player, protection):
            return {"protected": True, "card": protection}

        fraction = params["sell_fraction"]
        sell_price = params["sell_price_per_pen"]
        pens_sold = self.station.sell_fraction_stock(player.game_player_id, fraction)
        if pens_sold > 0:
            income = pens_sold * sell_price
            self.ledger.receive_from_bank(player, income, "card_stock_sale", turn_id)

        if params.get("restock_blocked"):
            from app.constants import BOARD_SIZE
            player.restock_blocked_until_circuit = True
            player.restock_block_spaces_remaining = BOARD_SIZE
            self.session.flush()

        return {"pens_sold": pens_sold, "income": pens_sold * sell_price if pens_sold > 0 else 0}

    def _effect_fire_fighting_equipment(self, player, params, turn_id):
        # This is a retainable card with purchase option
        # The decision to buy is handled by the pending action / decision service
        return {"purchase_price": params["purchase_price"], "retainable": True}

    def _effect_general_rain(self, player, params, turn_id):
        self.drought.break_all_droughts()
        return {"all_droughts_broken": True}

    def _effect_miss_turns(self, player, params, turn_id):
        player.visiting_town_turns = params["turns"]
        self.session.flush()
        return {"turns_to_miss": params["turns"]}

    def _effect_worm_infestation(self, player, params, turn_id):
        protection = params.get("protection_card")
        if protection and self._has_retained_card(player, protection):
            return {"protected": True, "card": protection}

        fraction = params["sell_fraction"]
        sell_price = params["sell_price_per_pen"]
        pens_sold = self.station.sell_fraction_stock(player.game_player_id, fraction)
        if pens_sold > 0:
            income = pens_sold * sell_price
            self.ledger.receive_from_bank(player, income, "card_stock_sale", turn_id)
        return {"pens_sold": pens_sold, "income": pens_sold * sell_price if pens_sold > 0 else 0}

    def _effect_local_rain(self, player, params, turn_id):
        was_in_drought = player.is_in_drought
        if was_in_drought:
            self.drought.break_drought(player, source="card_local_rain")
        return {"drought_broken": was_in_drought}

    def _effect_successful_lambing(self, player, params, turn_id):
        pens = params["pens"]
        cash_if_full = params["cash_if_full"]
        if self.station.is_fully_stocked(player.game_player_id):
            self.ledger.receive_from_bank(player, cash_if_full, "card_collect", turn_id)
            return {"cash_received": cash_if_full, "fully_stocked": True}
        else:
            added = self.station.buy_sheep(player.game_player_id, pens)
            self.station.declare_winner_if_eligible(player.game_player_id, turn_id)
            return {"pens_received": added, "fully_stocked": False}

    def _effect_receive_pens_and_bonus(self, player, params, turn_id):
        pens = params["pens"]
        cash_if_full = params["cash_if_full"]
        wool_bonus = params.get("wool_cheque_bonus", 0)

        if self.station.is_fully_stocked(player.game_player_id):
            self.ledger.receive_from_bank(player, cash_if_full, "card_collect", turn_id)
            result = {"cash_received": cash_if_full}
        else:
            added = self.station.buy_sheep(player.game_player_id, pens)
            self.station.declare_winner_if_eligible(player.game_player_id, turn_id)
            result = {"pens_received": added}

        if wool_bonus > 0:
            player.wool_cheque_bonus += wool_bonus
            self.session.flush()
            result["wool_cheque_bonus"] = wool_bonus

        return result

    def _effect_sustainable_water(self, player, params, turn_id):
        player.next_drought_halved = True
        self.session.flush()
        return {"next_drought_halved": True, "spaces": params["drought_halved_spaces"]}

    def _effect_grass_fire(self, player, params, turn_id):
        protection = params.get("protection_card")
        if protection and self._has_retained_card(player, protection):
            return {"protected": True, "card": protection}

        fraction = params["sell_fraction"]
        breakdown = self.station.sell_fraction_stock(
            player.game_player_id, fraction, return_breakdown=True
        )
        pens_sold = breakdown["total"]
        by_type = breakdown["by_type"]

        # Rule: "Sell half of all stock owned at Market price." Market price is
        # determined by drawing a Stock Sale card and applying its per-tier
        # selling prices to the pens removed from each pasture type.
        income = 0
        stock_card_used = None
        if pens_sold > 0:
            card = self.stock_sale.draw_stock_card(turn_id)
            income = (
                by_type["natural"] * card.sell_price_natural
                + by_type["improved"] * card.sell_price_improved_irrigated
                + by_type["irrigated"] * card.sell_price_improved_irrigated
            )
            self.ledger.receive_from_bank(
                player, income, "card_stock_sale", turn_id,
                notes=f"Grass Fire: sold {pens_sold} pens at Stock Sale prices",
            )
            stock_card_used = {
                "buy_price_per_pen": card.buy_price_per_pen,
                "sell_price_natural": card.sell_price_natural,
                "sell_price_improved_irrigated": card.sell_price_improved_irrigated,
            }

        if params.get("restock_blocked"):
            from app.constants import BOARD_SIZE
            player.restock_blocked_until_circuit = True
            player.restock_block_spaces_remaining = BOARD_SIZE
            self.session.flush()

        return {
            "pens_sold": pens_sold,
            "income": income,
            "by_type": by_type,
            "stock_card_used": stock_card_used,
        }

    def _effect_blowfly_wave(self, player, params, turn_id):
        # Wool cheque reduces by 10% unless player lands on Jet Sheep before next cheque
        # For now, set a flag
        reduction_pct = params["wool_reduction_pct"]
        player.wool_cheque_bonus -= int(self.station.get_total_pens(player.game_player_id)
                                        * 250 * reduction_pct / 100)
        self.session.flush()
        return {"wool_reduction_pct": reduction_pct}

    def _effect_high_stock_prices(self, player, params, turn_id):
        # Retainable: player keeps the card until they elect to apply +N%
        # to either buy or sell at a future Stock Sale.
        return {"price_modifier_pct": params["price_modifier_pct"], "retainable": True}

    def _effect_eradicate_footrot(self, player, params, turn_id):
        player.footrot_immune = True
        self.session.flush()
        return {"footrot_immune": True}

    def _effect_move_to_stock_sale(self, player, params, turn_id):
        # Find the next stock sale space after current position
        current = player.current_space_id
        stock_sales = (
            self.session.query(models.Space)
            .filter(models.Space.space_type == "stock_sale")
            .order_by(models.Space.board_index)
            .all()
        )
        next_sale = None
        for s in stock_sales:
            if s.board_index > current:
                next_sale = s
                break
        if next_sale is None and stock_sales:
            next_sale = stock_sales[0]  # wrap around

        if next_sale:
            player.current_space_id = next_sale.board_index
            self.session.flush()
            return {"moved_to": next_sale.name, "board_index": next_sale.board_index}
        return {"moved_to": None}

    def _effect_stud_ram_insurance(self, player, params, turn_id):
        # Retainable card — handled by retain_card
        return {"refund": params["refund"], "retainable": True}

    def _effect_agistment_fees(self, player, params, turn_id):
        if not self.station.is_fully_stocked(player.game_player_id):
            amount = params["amount"]
            self.ledger.receive_from_bank(player, amount, "agistment_fees", turn_id)
            return {"received": amount}
        return {"received": 0, "fully_stocked": True}

    def _effect_superfine_wool(self, player, params, turn_id):
        bonus = params["wool_cheque_bonus"]
        player.wool_cheque_bonus += bonus
        self.session.flush()
        return {"wool_cheque_bonus": bonus}

    # ── Helpers ──────────────────────────────────────────────────────────

    def _has_retained_card(self, player, card_name: str) -> bool:
        if not player or not card_name:
            return False
        draw = (
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
        return draw is not None
