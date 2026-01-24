from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app import models


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_game_or_404(game_id: int, session: Session) -> models.Game:
    """Validate game exists and return it, or raise 404."""
    game = session.query(models.Game).filter_by(game_id=game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    return game