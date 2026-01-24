from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api import deps
from app import models

router = APIRouter()

@router.get("/")
def list_ledger(game_id: int, limit: int = 50, session: Session = Depends(deps.get_session)):
    # Verify game exists
    deps.get_game_or_404(game_id, session)

    txns = (
        session.query(models.Transaction)
        .filter(models.Transaction.game_id == game_id)
        .order_by(models.Transaction.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": t.transaction_id,
            "type": t.transaction_type,
            "amount": t.amount,
            "from": t.player_from_id,
            "to": t.player_to_id,
            "created_at": t.created_at,
        }
        for t in txns
    ]

