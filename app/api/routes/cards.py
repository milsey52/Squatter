# app/api/routes/cards.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.deps import get_session
from app import models

router = APIRouter()


@router.get("/games/{game_id}/players/{player_id}/retained-cards")
def get_retained_cards(game_id: int, player_id: int, session: Session = Depends(get_session)):
    """Get all retained (not discarded) Tucker Bag cards for the player."""
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
    return [
        {
            "card_draw_id": d.card_draw_id,
            "title": d.card.title,
            "body_text": d.card.body_text,
            "deck_type": d.deck_type,
            "draw_order": d.draw_order,
        }
        for d in draws
    ]


@router.get("/games/{game_id}/player_retained_cards")
def get_all_player_retained_cards(game_id: int, session: Session = Depends(get_session)):
    """Get all retained cards for all players in a game, keyed by player_id."""
    draws = (
        session.query(models.CardDraw)
        .join(models.Card, models.CardDraw.card_id == models.Card.card_id)
        .filter(
            models.CardDraw.game_id == game_id,
            models.CardDraw.kept_by_player_id.isnot(None),
            models.CardDraw.discarded_at.is_(None),
        )
        .all()
    )

    result = {}
    for draw in draws:
        player_id = draw.kept_by_player_id
        if player_id not in result:
            result[player_id] = []
        result[player_id].append({
            "card_draw_id": draw.card_draw_id,
            "title": draw.card.title,
            "body_text": draw.card.body_text,
            "deck_type": draw.deck_type,
            "draw_order": draw.draw_order,
        })

    return result


@router.get("/games/{game_id}/last_drawn_card")
def get_last_drawn_card(game_id: int, session: Session = Depends(get_session)):
    """Get the most recently drawn Tucker Bag card."""
    draw = (
        session.query(models.CardDraw)
        .join(models.Card, models.CardDraw.card_id == models.Card.card_id)
        .filter(
            models.CardDraw.game_id == game_id,
            models.CardDraw.deck_type == "tucker_bag"
        )
        .order_by(models.CardDraw.draw_order.desc())
        .first()
    )

    if draw:
        return {
            "title": draw.card.title,
            "body_text": draw.card.body_text,
            "draw_order": draw.draw_order,
        }

    return None
