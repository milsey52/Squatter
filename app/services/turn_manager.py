# app/services/turn_manager.py
import random
from typing import Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from .space_resolver import SpaceResolver
from .card_service import CardService
from .ledger_service import LedgerService
from app import models


class TurnManager:
    def __init__(self, session: Session, game_id: int):
        self.session = session
        self.game_id = game_id

        # create resolver first (no card service yet)
        self.space_resolver = SpaceResolver(session, game_id)

        # create card service, passing resolver
        self.card_service = CardService(session, game_id, space_resolver=self.space_resolver)

        # link resolver back to card service
        self.space_resolver.card_service = self.card_service

        self.ledger = LedgerService(session, game_id)

    # Public entry point -------------------------------------------------
    def play_turn(self) -> None:
        player = self._current_player()
        if player is None:
            raise RuntimeError("No active player for this game.")

        d1, d2 = self._roll_dice()
        is_double = d1 == d2

        turn = self._start_turn(player, d1, d2, is_double)

        # Jail logic first
        if self._handle_jail(player, d1, d2, is_double, turn):
            self._maybe_advance_turn(player, is_double)
            return

        end_space, passed_start = self._move_player(player, d1 + d2)

        self.space_resolver.resolve(player, end_space, turn, passed_start)

        self._maybe_advance_turn(player, is_double)

    # Dice utilities -----------------------------------------------------
    @staticmethod
    def _roll_dice() -> Tuple[int, int]:
        return random.randint(1, 6), random.randint(1, 6)

    # Turn helpers -------------------------------------------------------


    def _start_turn(self, player, d1, d2, is_double) -> models.Turn:
        turn_number = self._next_turn_number()
        turn = models.Turn(
            game_id=self.game_id,
            turn_number=turn_number,
            active_game_player_id=player.game_player_id,
            dice_roll_1=d1,
            dice_roll_2=d2,
            is_double=is_double,
            double_count=self._update_double_streak(player, is_double),
        )
        self.session.add(turn)
        self.session.flush()
        return turn

    def _next_turn_number(self) -> int:
        q = (
            self.session.query(func.max(models.Turn.turn_number))
            .filter(models.Turn.game_id == self.game_id)
        ).scalar()
        return (q or 0) + 1

    def _update_double_streak(self, player, is_double: bool) -> int:
        # player.double_streak column should exist (default 0)
        streak = player.double_streak or 0
        streak = streak + 1 if is_double else 0
        player.double_streak = streak
        return streak

    # Jail logic ---------------------------------------------------------
    def _handle_jail(self, player, d1, d2, is_double, turn) -> bool:
        if not player.in_jail:
            return False

        player.jail_turns += 1

        if is_double:
            player.in_jail = False
            player.jail_turns = 0
            return False

        if self._player_has_get_out_of_jail_card(player):
            self._consume_get_out_card(player, turn)
            player.in_jail = False
            player.jail_turns = 0
            return False

        if player.jail_turns >= 3:
            self.ledger.record_bank_payment(player, 500, "jail_fine", turn.turn_id)
            player.in_jail = False
            player.jail_turns = 0
            self._move_player(player, d1 + d2)
            return True

        # otherwise player stays in jail, turn ends
        return True

    # Movement -----------------------------------------------------------
    def _move_player(self, player, steps: int) -> Tuple[models.Space, bool]:
        start_space = player.current_space_id
        end_space_idx = (start_space + steps) % 40
        passed_start = (start_space + steps) >= 40
        player.current_space_id = end_space_idx

        movement = models.Movement(
            turn_id=self._current_turn_id(player),
            game_player_id=player.game_player_id,
            start_space_id=start_space,
            end_space_id=end_space_idx,
            movement_type="roll",
            distance=steps,
            passed_start=passed_start,
        )
        self.session.add(movement)
        self.session.flush()

        if passed_start:
            self.ledger.record_pass_start_bonus(player)

        return (
            self.session.query(models.Space)
            .filter(models.Space.board_index == end_space_idx)
            .one(),
            passed_start,
        )

    def _current_turn_id(self, player) -> Optional[int]:
        turn = (
            self.session.query(models.Turn)
            .filter_by(game_id=self.game_id, active_game_player_id=player.game_player_id)
            .order_by(models.Turn.turn_number.desc())
            .first()
        )
        return turn.turn_id if turn else None

    # Player rotation ----------------------------------------------------
    def _maybe_advance_turn(self, player, is_double):
        if is_double and player.double_streak < 3 and not player.in_jail:
            # same player goes again
            return

        if player.double_streak >= 3:
            # send to jail
            player.in_jail = True
            player.jail_turns = 0
            player.current_space_id = self._jail_space_id()

        player.double_streak = 0
        next_player = self._next_player(player)
        self._set_current_player(next_player)
        self.session.flush()

    def _next_player(self, current_player):
        players = (
            self.session.query(models.GamePlayer)
            .filter_by(game_id=self.game_id, is_active=True)
            .order_by(models.GamePlayer.turn_order)
            .all()
        )
        if not players:
            raise RuntimeError("No active players in game.")
        idx = next(i for i, p in enumerate(players) if p.game_player_id == current_player.game_player_id)
        return players[(idx + 1) % len(players)]

    def _set_current_player(self, player):
        # simplest approach: store “current player id” on Game table
        game = self.session.query(models.Game).get(self.game_id)
        game.current_game_player_id = player.game_player_id

    # Helpers ------------------------------------------------------------
    def _current_player(self):
        players = self._active_players_ordered()
        if not players:
            raise RuntimeError("No active players in this game.")

        game = self.session.query(models.Game).get(self.game_id)

        # Use explicitly tracked current player if set
        if game.current_game_player_id:
            for player in players:
                if player.game_player_id == game.current_game_player_id:
                    return player

        # Fallback: first turn of the game or current player was removed
        return players[0]

    def _jail_space_id(self) -> int:
        # hardcode or look up "Police Arrest – Imprisonment"
        return 31  # adjust if different

    def _player_has_get_out_of_jail_card(self, player) -> bool:
        card = (
            self.session.query(models.CardDraw)
            .join(models.Card)
            .filter(
                models.CardDraw.game_id == self.game_id,
                models.CardDraw.kept_by_player_id == player.game_player_id,
                models.Card.effect_code == "GET_OUT_OF_JAIL",
                models.CardDraw.discarded_at.is_(None),
            )
            .first()
        )
        return card is not None

    def _consume_get_out_card(self, player, turn):
        card_draw = (
            self.session.query(models.CardDraw)
            .join(models.Card)
            .filter(
                models.CardDraw.game_id == self.game_id,
                models.CardDraw.kept_by_player_id == player.game_player_id,
                models.Card.effect_code == "GET_OUT_OF_JAIL",
                models.CardDraw.discarded_at.is_(None),
            )
            .first()
        )
        if card_draw:
            card_draw.kept_by_player_id = None
            card_draw.discarded_at = turn.started_at
            self.session.flush()

    def _active_players_ordered(self):
        return (
            self.session.query(models.GamePlayer)
            .filter_by(game_id=self.game_id, is_active=True)
            .order_by(models.GamePlayer.turn_order)
            .all()
        )
    
    def _last_turn(self):
        return (
            self.session.query(models.Turn)
            .filter(models.Turn.game_id == self.game_id)
            .order_by(models.Turn.turn_number.desc())
            .first()
        )
    
    def _set_next_player(self, current_player):
        players = self._active_players_ordered()
        if not players:
            return

        idx = next(
            (i for i, p in enumerate(players) if p.game_player_id == current_player.game_player_id),
            None,
        )
        if idx is None:
            return

        next_player = players[(idx + 1) % len(players)]
        turn = self._last_turn()
        if turn:
            turn.active_game_player_id = current_player.game_player_id  # already set