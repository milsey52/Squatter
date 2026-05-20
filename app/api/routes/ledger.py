# app/api/routes/ledger.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api import deps
from app import models

router = APIRouter()


@router.get("")
def list_ledger(game_id: int, limit: int = 50, session: Session = Depends(deps.get_session)):
    """Get recent transactions for the game."""
    deps.get_game_or_404(game_id, session)

    PlayerFrom = models.GamePlayer.__table__.alias('player_from')
    PlayerTo = models.GamePlayer.__table__.alias('player_to')

    txns = (
        session.query(
            models.Transaction,
            PlayerFrom.c.player_name.label("from_player_name"),
            PlayerTo.c.player_name.label("to_player_name")
        )
        .outerjoin(PlayerFrom, models.Transaction.player_from_id == PlayerFrom.c.game_player_id)
        .outerjoin(PlayerTo, models.Transaction.player_to_id == PlayerTo.c.game_player_id)
        .filter(models.Transaction.game_id == game_id)
        .order_by(models.Transaction.transaction_id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": t.Transaction.transaction_id,
            "type": t.Transaction.transaction_type,
            "amount": t.Transaction.amount,
            "from": t.from_player_name or "Bank",
            "to": t.to_player_name or "Bank",
            "notes": t.Transaction.notes,
            "created_at": t.Transaction.created_at,
        }
        for t in txns
    ]
