# app/services/game_service.py
from sqlalchemy.orm import Session
from app import models
from app.constants import DEFAULT_STARTING_CASH, QUICK_GAME_STARTING_CASH
from app.services.station_service import StationService


def initialize_game_state(session: Session, game_id: int, quick_game: bool = False):
    """Initialize paddocks and stud ram states for a new game."""
    station_svc = StationService(session, game_id)

    # Create paddocks for each player
    players = (
        session.query(models.GamePlayer)
        .filter_by(game_id=game_id)
        .all()
    )
    for player in players:
        station_svc.initialize_station(player.game_player_id, quick_game=quick_game)

    # Create stud ram states (all 5 unowned)
    station_svc.initialize_stud_ram_states()
    session.flush()


def create_game_with_defaults(session: Session, host_user_id: int, player_names: list):
    """Create a full game with players, rules, and initial state."""
    game = models.Game(host_user_id=host_user_id, status="in_progress")
    session.add(game)
    session.flush()

    for order, name in enumerate(player_names, start=1):
        session.add(models.GamePlayer(
            game_id=game.game_id,
            player_name=name,
            turn_order=order,
            current_board_index=0,
        ))

    session.add(models.GameRule(
        game_id=game.game_id,
        starting_cash=DEFAULT_STARTING_CASH,
        quick_game=False,
        starting_paddock_type="natural",
    ))

    session.flush()
    initialize_game_state(session, game.game_id)
    session.commit()

    return game.game_id
