# app/services/drought_service.py
from sqlalchemy.orm import Session
from app import models
from app.constants import BOARD_SIZE


class DroughtService:
    def __init__(self, session: Session, game_id: int):
        self.session = session
        self.game_id = game_id

    def apply_drought(self, player: models.GamePlayer, board_index: int):
        """Apply local drought to a player. Haystack consumption (if any) is
        handled by the caller (see space_resolver._handle_local_drought) since
        per the rules a haystack is only "used" when it actually offsets a sale.

        Rule: landing on a Local Drought (whether new or while already in
        drought) requires a fresh full circuit (BOARD_SIZE spaces) to clear.
        Per-player "next drought halved" only applies on the very first
        drought (consumed there); a subsequent extension still requires
        the full circuit.
        """
        if player.is_in_drought:
            # Restart the clock from this space — another full circuit.
            player.drought_spaces_remaining = BOARD_SIZE
            player.drought_start_space = board_index
        else:
            player.is_in_drought = True
            player.drought_start_space = board_index
            if player.next_drought_halved:
                player.drought_spaces_remaining = BOARD_SIZE // 2
                player.next_drought_halved = False
            else:
                player.drought_spaces_remaining = BOARD_SIZE

        self.session.flush()

    def track_movement(self, player: models.GamePlayer, spaces_moved: int):
        """After each move, decrement drought counter. Break if complete."""
        if not player.is_in_drought:
            return

        player.drought_spaces_remaining -= spaces_moved
        if player.drought_spaces_remaining <= 0:
            self.break_drought(player, source="circuit_complete")

        self.session.flush()

    def break_drought(self, player: models.GamePlayer, source: str = "rain"):
        """Break drought on a player's property."""
        if not player.is_in_drought:
            return

        player.is_in_drought = False
        player.drought_start_space = None
        player.drought_spaces_remaining = 0
        self.session.flush()

    def break_all_droughts(self):
        """General Rain — breaks drought on ALL stations."""
        players = (
            self.session.query(models.GamePlayer)
            .filter_by(game_id=self.game_id, is_active=True, is_in_drought=True)
            .all()
        )
        for player in players:
            self.break_drought(player, source="general_rain")

    def apply_bore_dries_up(self, player: models.GamePlayer):
        """Bore Dries Up — only affects players with irrigated pasture.
        Must sell half stock on Natural/Improved to bank."""
        has_irrigated = (
            self.session.query(models.Paddock)
            .filter_by(
                game_id=self.game_id,
                owner_game_player_id=player.game_player_id,
                paddock_type="irrigated",
            )
            .first()
        )
        if not has_irrigated:
            return False  # Not affected

        player.bore_dried_up = True
        self.session.flush()
        return True

    def is_drought_restricted(self, player: models.GamePlayer) -> bool:
        """Check if player is under drought restrictions
        (cannot buy stock, cannot upgrade paddocks, cannot sell stud rams)."""
        return player.is_in_drought

    def is_restock_blocked(self, player: models.GamePlayer) -> bool:
        """Check if player is blocked from restocking (due to Tucker Bag card effects)."""
        return player.restock_blocked_until_circuit
