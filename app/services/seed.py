# app/services/seed.py
from app.services.game_service import initialize_game_state


def seed_game_state(session, game_id: int, quick_game: bool = False):
    """Seed initial game state (paddocks and stud ram states)."""
    initialize_game_state(session, game_id, quick_game=quick_game)
