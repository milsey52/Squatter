from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.deps import get_session
from app import models

router = APIRouter()

@router.get("/games/{game_id}/players/{player_id}/retained-cards")
def get_retained_cards(game_id: int, player_id: int, session: Session = Depends(get_session)):
    # Get all retained (not discarded) cards for the player in the game
    draws = (
        session.query(models.CardDraw)
        .join(models.Card, models.CardDraw.card_id == models.Card.card_id)
        .filter(
            models.CardDraw.game_id == game_id,
            models.CardDraw.kept_by_player_id == player_id,
            models.CardDraw.discarded_at.is_(None),
        )
        .all()
    )
    # Return card info
    return [
        {
            "title": d.card.title,
            "body_text": d.card.body_text,
            "deck_type": d.deck_type,
            "draw_order": d.draw_order,
        }
        for d in draws
    ]


@router.get("/games/{game_id}/last_drawn_cards")
def get_last_drawn_cards(game_id: int, session: Session = Depends(get_session)):
    """Get the most recently drawn card for each deck type (CHANCE, WELFARE)"""
    result = {"CHANCE": None, "WELFARE": None}

    for deck_type in ["CHANCE", "WELFARE"]:
        draw = (
            session.query(models.CardDraw)
            .join(models.Card, models.CardDraw.card_id == models.Card.card_id)
            .filter(
                models.CardDraw.game_id == game_id,
                models.CardDraw.deck_type == deck_type
            )
            .order_by(models.CardDraw.draw_order.desc())
            .first()
        )

        if draw:
            result[deck_type] = {
                "title": draw.card.title,
                "body_text": draw.card.body_text,
                "draw_order": draw.draw_order,
            }

    return result