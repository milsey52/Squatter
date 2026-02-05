from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api import deps
from app.services.jackpot_service import JackpotService

router = APIRouter()

@router.get("")
def get_jackpot(game_id: int, session: Session = Depends(deps.get_session)):
    # Verify game exists
    deps.get_game_or_404(game_id, session)

    jackpot = JackpotService(session, game_id)
    return {"jackpot": jackpot.current_balance()}