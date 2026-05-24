# app/services/turn_manager.py
import random
from typing import Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app import models
from app.constants import BOARD_SIZE
from .space_resolver import SpaceResolver
from .card_service import CardService
from .ledger_service import LedgerService
from .drought_service import DroughtService


class TurnManager:
    def __init__(self, session: Session, game_id: int):
        self.session = session
        self.game_id = game_id

        # Create resolver first (no card service yet)
        self.space_resolver = SpaceResolver(session, game_id)

        # Create card service, passing resolver
        self.card_service = CardService(session, game_id, space_resolver=self.space_resolver)

        # Link resolver back to card service
        self.space_resolver.card_service = self.card_service

        self.ledger = LedgerService(session, game_id)
        self.drought = DroughtService(session, game_id)

    # Public entry point -------------------------------------------------
    def play_turn(self) -> None:
        player = self._current_player()
        if player is None:
            raise RuntimeError("No active player for this game.")

        # Visiting Town: skip turn and decrement counter
        if player.visiting_town_turns and player.visiting_town_turns > 0:
            self._handle_visiting_town(player)
            return

        d1, d2 = self._roll_dice()
        is_double = d1 == d2

        turn = self._start_turn(player, d1, d2, is_double)

        end_space, passed_start = self._move_player(player, d1 + d2, turn)

        # Track drought movement (decrement spaces remaining)
        if player.is_in_drought and player.drought_spaces_remaining > 0:
            self.drought.track_movement(player, d1 + d2)

        self.space_resolver.resolve(player, end_space, turn, passed_start)

        self._maybe_advance_turn(player, is_double)

    # Dice utilities -----------------------------------------------------
    @staticmethod
    def _roll_dice() -> Tuple[int, int]:
        return random.randint(1, 6), random.randint(1, 6)

    # Turn helpers -------------------------------------------------------

    def _handle_visiting_town(self, player):
        """Player is missing a turn — record a no-roll, no movement."""
        turn = self._start_turn(player, 0, 0, False)

        player.visiting_town_turns -= 1
        self.session.flush()

        next_player = self._next_player(player)
        self._set_current_player(next_player)
        self.session.flush()

    def _start_turn(self, player, d1, d2, is_double) -> models.Turn:
        turn_number = self._next_turn_number()
        turn = models.Turn(
            game_id=self.game_id,
            turn_number=turn_number,
            active_game_player_id=player.game_player_id,
            dice_roll_1=d1,
            dice_roll_2=d2,
            is_double=is_double,
            double_count=0,
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

    # Movement -----------------------------------------------------------
    def _move_player(self, player, steps: int, turn: models.Turn) -> Tuple[models.Space, bool]:
        start_board_idx = player.current_space_id
        end_board_idx = (start_board_idx + steps) % BOARD_SIZE
        passed_start = (start_board_idx + steps) >= BOARD_SIZE

        player.current_space_id = end_board_idx

        # Look up actual space records
        start_space = (
            self.session.query(models.Space)
            .filter(models.Space.board_index == start_board_idx)
            .first()
        )
        end_space = (
            self.session.query(models.Space)
            .filter(models.Space.board_index == end_board_idx)
            .first()
        )

        if end_space is None:
            raise ValueError(f"No space found for board_index={end_board_idx}")

        movement = models.Movement(
            turn_id=turn.turn_id,
            game_player_id=player.game_player_id,
            start_space_id=start_space.space_id if start_space else 1,
            end_space_id=end_space.space_id,
            movement_type="roll",
            distance=steps,
            passed_start=passed_start,
        )
        self.session.add(movement)
        self.session.flush()

        # Decrement the restock-block counter (used by Bore Dries Up — full
        # circuit by default, or halved 22 if Sustainable Water was queued).
        if player.restock_blocked_until_circuit:
            if player.restock_block_spaces_remaining > 0:
                player.restock_block_spaces_remaining -= steps
            if (player.restock_block_spaces_remaining <= 0) or passed_start:
                player.restock_blocked_until_circuit = False
                player.restock_block_spaces_remaining = 0
                player.restock_block_scope = None
                player.bore_dried_up = False
            self.session.flush()

        return (end_space, passed_start)

    # Player rotation ----------------------------------------------------
    def _maybe_advance_turn(self, player, is_double):
        # Per Squatter manual p.4: "Players are permitted only one throw of
        # the dice each turn; Doubles do not entitle a Player to a second throw."
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
        game = self.session.query(models.Game).get(self.game_id)
        game.current_game_player_id = player.game_player_id

    # Helpers ------------------------------------------------------------
    def _current_player(self):
        players = self._active_players_ordered()
        if not players:
            raise RuntimeError("No active players in this game.")

        game = self.session.query(models.Game).get(self.game_id)

        if game.current_game_player_id:
            for player in players:
                if player.game_player_id == game.current_game_player_id:
                    return player

        # Fallback: first turn of the game
        return players[0]

    def _active_players_ordered(self):
        return (
            self.session.query(models.GamePlayer)
            .filter_by(game_id=self.game_id, is_active=True)
            .order_by(models.GamePlayer.turn_order)
            .all()
        )
