from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api import deps
from app import models

router = APIRouter()

@router.get("/")
def list_ledger(game_id: int, limit: int = 50, session: Session = Depends(deps.get_session)):
    # Verify game exists
    deps.get_game_or_404(game_id, session)

    # Alias for the two player joins
    PlayerFrom = models.GamePlayer.__table__.alias('player_from')
    UserFrom = models.User.__table__.alias('user_from')
    PlayerTo = models.GamePlayer.__table__.alias('player_to')
    UserTo = models.User.__table__.alias('user_to')

    txns = (
        session.query(
            models.Transaction,
            models.Space.name.label("asset_name"),
            UserFrom.c.display_name.label("from_player_name"),
            UserTo.c.display_name.label("to_player_name")
        )
        .outerjoin(models.Asset, models.Transaction.asset_id == models.Asset.asset_id)
        .outerjoin(models.Space, models.Asset.space_id == models.Space.space_id)
        .outerjoin(PlayerFrom, models.Transaction.player_from_id == PlayerFrom.c.game_player_id)
        .outerjoin(UserFrom, PlayerFrom.c.user_id == UserFrom.c.user_id)
        .outerjoin(PlayerTo, models.Transaction.player_to_id == PlayerTo.c.game_player_id)
        .outerjoin(UserTo, PlayerTo.c.user_id == UserTo.c.user_id)
        .filter(models.Transaction.game_id == game_id)
        .order_by(models.Transaction.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": t.Transaction.transaction_id,
            "type": t.Transaction.transaction_type,
            "amount": t.Transaction.amount,
            "from": t.from_player_name,
            "to": t.to_player_name,
            "asset_name": t.asset_name,
            "created_at": t.Transaction.created_at,
        }
        for t in txns
    ]

