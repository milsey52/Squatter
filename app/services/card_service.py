# app/services/card_service.py

import json
import random
from typing import Optional, TYPE_CHECKING

from sqlalchemy.orm import Session
from sqlalchemy import func, literal

if TYPE_CHECKING:
    from .space_resolver import SpaceResolver

from app import models
from app.constants import BOARD_SIZE, JAIL_SPACE_ID
from .ledger_service import LedgerService
from .jackpot_service import JackpotService


class CardService:
    def __init__(self, session: Session, game_id: int, space_resolver: "SpaceResolver"):
        self.session = session
        self.game_id = game_id
        self.ledger = LedgerService(session, game_id)
        self.jackpot = JackpotService(session, game_id)
        self.space_resolver = space_resolver

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def draw_and_apply(self, player, deck_type: str, turn):
        card_draw = self._draw_card(deck_type, turn.turn_id)
        card = self.session.query(models.Card).get(card_draw.card_id)

        if card.is_retainable:
            card_draw.kept_by_player_id = player.game_player_id
            self.session.flush()
            return card

        self._apply_effect(card, player, turn)

        card_draw.discarded_at = turn.started_at
        self.session.flush()
        return card

    # ------------------------------------------------------------------
    # Drawing / deck helpers
    # ------------------------------------------------------------------
    def _draw_card(self, deck_type: str, turn_id: int) -> models.CardDraw:
        deck = self._shuffled_deck(deck_type)
        card = deck.pop(0)

        draw = models.CardDraw(
            game_id=self.game_id,
            turn_id=turn_id,
            deck_type=deck_type,
            card_id=card.card_id,
            draw_order=self._next_draw_order(deck_type),
        )
        self.session.add(draw)
        self.session.flush()
        return draw

    def _shuffled_deck(self, deck_type: str):
        cards = (
            self.session.query(models.Card)
            .filter(models.Card.deck_type == deck_type)
            .order_by(models.Card.card_id)
            .all()
        )
        random.shuffle(cards)
        return cards

    def _next_draw_order(self, deck_type: str) -> int:
        count = (
            self.session.query(func.count(models.CardDraw.card_draw_id))
            .filter(
                models.CardDraw.game_id == self.game_id,
                models.CardDraw.deck_type == deck_type,
            )
            .scalar()
        )
        return count + 1

    # ------------------------------------------------------------------
    # Effect dispatcher
    # ------------------------------------------------------------------
    def _apply_effect(self, card: models.Card, player, turn):
        code = card.effect_code or "UNKNOWN"
        params = json.loads(card.effect_params or "{}")

        if code == "COLLECT":
            self._effect_collect(player, params, turn)

        elif code == "PAY_BANK":
            self._effect_pay_bank(player, params, turn)

        elif code == "PAY_REPAIRS":
            self._effect_pay_repairs(player, params, turn)

        elif code == "COLLECT_FROM_EACH_PLAYER":
            self._effect_collect_each(player, params, turn)

        elif code == "PAY_EACH_PLAYER":
            self._effect_pay_each(player, params, turn)

        elif code == "GO_TO_JAIL":
            self._effect_go_to_jail(player, turn)

        elif code == "ADVANCE_TO":
            space_name = params.get("space_name")
            if space_name:
                # Find the space by name
                space = self.session.query(models.Space).filter(
                    models.Space.name.ilike(f"%{space_name}%")
                ).first()
                if space:
                    collect_bonus = params.get("collect_pass_bonus", False)
                    self._move_player_to_space(player, space.space_id, turn, allow_pass_bonus=collect_bonus)
                    # Check if we need to resolve landing on the space
                    passed_start = self._passed_start(player.current_space_id, space.board_index)
                    self.space_resolver.resolve(player, space, turn, passed_start)

        elif code == "MOVE_TO":
            self._effect_move_to(player, params, turn)

        elif code == "MOVE_BACK":
            self._effect_move_back(player, params, turn)

        elif code == "MOVE_RELATIVE":
            self._effect_move_back(player, params, turn)

        elif code == "ADVANCE_NEAREST":
            space_type = params.get("space_type", "transport")
            self._effect_advance_nearest(player, space_type, params, turn)

        elif code == "ADVANCE_NEAREST_TRANSPORT":
            self._effect_advance_nearest(player, "transport", params, turn)

        elif code == "ADVANCE_NEAREST_UTILITY":
            self._effect_advance_nearest(player, "utility", params, turn)

        elif code == "JACK-POT":
            self._effect_jack_pot(player, params, turn)

        elif code == "GET_OUT_OF_JAIL":
            # Retain-only cards are handled in draw_and_apply
            pass

        else:
            print(f"[CardService] Unhandled effect_code: {code}")

    # ------------------------------------------------------------------
    # Individual effect handlers
    # ------------------------------------------------------------------
    def _effect_collect(self, player, params, turn):
        amount = params.get("amount", 0)
        if amount > 0:
            self.ledger.record_bank_reward(player, amount, "card_collect", turn.turn_id)

    def _effect_jack_pot(self, player, params, turn):
        amount = params.get("amount", 0)
        if amount <= 0:
            return

        txn = self.ledger.record_bank_payment(
            player,
            amount,
            txn_type="card_penalty",
            turn_id=turn.turn_id,
        )

        self.jackpot.contribute(amount, turn.turn_id, txn.transaction_id)

    def _effect_pay_bank(self, player, params, turn):
        amount = params.get("amount", 0)
        if amount <= 0:
            return

        txn = self.ledger.record_bank_payment(
            player,
            amount,
            txn_type="card_penalty",
            turn_id=turn.turn_id,
        )

        if params.get("jackpot"):
            self.jackpot.contribute(amount, turn.turn_id, txn.transaction_id)

    def _effect_pay_repairs(self, player, params, turn):
        per_house = params.get("per_house", 0)
        per_hotel = params.get("per_hotel", 0)
        houses, hotels = self._count_buildings(player.game_player_id)
        amount = houses * per_house + hotels * per_hotel
        if amount <= 0:
            return
        self.ledger.record_bank_payment(player, amount, "repairs", turn.turn_id)

    def _effect_collect_each(self, player, params, turn):
        amount = params.get("amount", 0)
        if amount <= 0:
            return
        others = self._other_players(player.game_player_id)
        for other in self._other_players(player.game_player_id):
            self.ledger.transfer(
                payer=other,
                payee_id=player.game_player_id,
                amount=amount,
                txn_type="card_collect_each",
                turn_id=turn.turn_id,
            )

    def _effect_pay_each(self, player, params, turn):
        amount = params.get("amount", 0)
        if amount <= 0:
            return
        others = self._other_players(player.game_player_id)
        for other in self._other_players(player.game_player_id):
            self.ledger.transfer(
                payer=player,
                payee_id=other.game_player_id,
                amount=amount,
                txn_type="card_pay_each",
                turn_id=turn.turn_id,
            )

    def _effect_go_to_jail(self, player, turn):
        start_idx = player.current_space_id
        jail_idx = JAIL_SPACE_ID  # Already a board_index (10 = Visit Jail)
        player.current_space_id = jail_idx
        player.in_jail = True
        player.jail_turns = 0
        self._log_movement(player, start_idx, jail_idx, turn, "card", passed_start=False)

    def _effect_move_to(self, player, params, turn):
        target_space_id = params.get("space_id")
        if not target_space_id:
            return
        allow_pass_bonus = params.get("allow_pass_bonus", False)
        collect_on_land = params.get("collect_on_land")
        space = self._move_player_to_space(player, target_space_id, turn, allow_pass_bonus)

        if collect_on_land:
            self.ledger.record_bank_reward(player, collect_on_land, "card_bonus", turn.turn_id)

        self._resolve_post_move(space, player, params, turn)

    def _effect_move_back(self, player, params, turn):
        steps = params.get("steps", -3)
        current_idx = player.current_space_id
        # Simple modulo arithmetic with 0-based indexing (board uses indices 0-39)
        new_idx = (current_idx + steps) % BOARD_SIZE
        passed_start = steps > 0 and (current_idx + steps) >= BOARD_SIZE

        player.current_space_id = new_idx
        player.in_jail = False

        self._log_movement(player, current_idx, new_idx, turn, "card", passed_start)

        # After moving, reuse space resolver logic (buy/rent, etc.)
        space = self._space_by_board_index(new_idx)
        self._resolve_post_move(space, player, params, turn)

    def _effect_advance_nearest(self, player, space_type, params, turn):
        target_space_id = self._nearest_space_id(player.current_space_id, space_type)
        if target_space_id is None:
            return
        space = self._move_player_to_space(player, target_space_id, turn, allow_pass_bonus=True)
        self._resolve_post_move(space, player, params, turn)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _move_player_to_space(self, player, space_id: int, turn, allow_pass_bonus: bool):
        target = self._space_by_id(space_id)
        current_idx = player.current_space_id
        target_idx = target.board_index

        passed_start = self._passed_start(current_idx, target_idx)
        player.current_space_id = target_idx
        player.in_jail = False
        player.jail_turns = 0

        self._log_movement(player, current_idx, target_idx, turn, "card", passed_start)

        if passed_start and allow_pass_bonus:
            self.ledger.record_pass_start_bonus(player, turn.turn_id)

        return target

    def _move_player_relative(self, player, steps: int, turn):
        current_idx = player.current_space_id
        # Simple modulo arithmetic with 0-based indexing (board uses indices 0-39)
        new_idx = (current_idx + steps) % BOARD_SIZE
        passed_start = steps > 0 and (current_idx + steps) >= BOARD_SIZE

        player.current_space_id = new_idx
        player.in_jail = False

        self._log_movement(player, current_idx, new_idx, turn, "card", passed_start)

    def _resolve_post_move(self, space, player, params, turn):
        rent_multiplier = params.get("rent_multiplier")
        skip_cards = params.get("skip_card_draw", True)

        # Use SpaceResolver to apply property/utility logic with temporary rules
        self.space_resolver.resolve_from_card(
            player=player,
            space=space,
            turn=turn,
            passed_start=False,
            rent_multiplier=rent_multiplier,
            skip_cards=skip_cards,
        )

    def _log_movement(self, player, start_idx, end_idx, turn, movement_type, passed_start):
        distance = (end_idx - start_idx) % BOARD_SIZE
        # Convert board_index to space_id for FK constraints
        start_space = self._space_by_board_index(start_idx)
        end_space = self._space_by_board_index(end_idx)
        movement = models.Movement(
            turn_id=turn.turn_id if turn else None,
            game_player_id=player.game_player_id,
            start_space_id=start_space.space_id,
            end_space_id=end_space.space_id,
            movement_type=movement_type,
            distance=distance,
            passed_start=1 if passed_start else 0,
        )
        self.session.add(movement)

    def _passed_start(self, start_idx, end_idx) -> bool:
        return end_idx < start_idx

    def _space_by_id(self, space_id: int) -> models.Space:
        space = self.session.query(models.Space).filter_by(space_id=space_id).first()
        if space is None:
            raise ValueError(f"No space found for space_id={space_id}")
        return space

    def _space_by_board_index(self, board_index: int) -> models.Space:
        space = (
            self.session.query(models.Space)
            .filter(models.Space.board_index == board_index)
            .first()
        )
        if space is None:
            raise ValueError(f"No space found for board_index={board_index}")
        return space

    def _to_board_index(self, space_id: int) -> int:
        space = self._space_by_id(space_id)
        return space.board_index

    def _nearest_space_id(self, current_idx: int, space_type: str) -> Optional[int]:
        spaces = (
            self.session.query(models.Space)
            .filter(models.Space.space_type == space_type)
            .order_by(models.Space.board_index)
            .all()
        )
        if not spaces:
            return None
        for space in spaces:
            if space.board_index > current_idx:
                return space.space_id
        return spaces[0].space_id  # wrap around

    def _count_buildings(self, game_player_id: int):
        houses = (
            self.session.query(func.coalesce(func.sum(models.AssetState.improvement_level), 0))
            .filter(
                models.AssetState.game_id == self.game_id,
                models.AssetState.owner_game_player_id == game_player_id,
            )
            .scalar()
        )
        hotels = (
            self.session.query(func.coalesce(func.sum(literal(1)), 0))
            .filter(
                models.AssetState.game_id == self.game_id,
                models.AssetState.owner_game_player_id == game_player_id,
                models.AssetState.has_hotel == True,
            )
            .scalar()
        )
        return houses or 0, hotels or 0

    def _other_players(self, exclude_game_player_id: int):
        return (
            self.session.query(models.GamePlayer)
            .filter(
                models.GamePlayer.game_id == self.game_id,
                models.GamePlayer.game_player_id != exclude_game_player_id,
                models.GamePlayer.is_active == True,
            )
            .all()
        )