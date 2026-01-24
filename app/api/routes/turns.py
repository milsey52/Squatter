from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.services.turn_manager import TurnManager
from app.api import deps
from app import models

router = APIRouter()

@router.post("/")
def play_turn(game_id: int, session: Session = Depends(deps.get_session)):
    # Verify game exists
    deps.get_game_or_404(game_id, session)

    tm = TurnManager(session, game_id)
    tm.play_turn()
    session.commit()

    turn = (
        session.query(models.Turn)
        .filter(models.Turn.game_id == game_id)
        .order_by(models.Turn.turn_number.desc())
        .first()
    )

    if not turn:
        raise HTTPException(status_code=500, detail="Turn was not recorded")

    return {
        "turn_number": turn.turn_number,
        "player_id": turn.active_game_player_id,
        "dice_roll_1": turn.dice_roll_1,
        "dice_roll_2": turn.dice_roll_2,
        "total_roll": turn.dice_roll_1 + turn.dice_roll_2 if turn.dice_roll_1 and turn.dice_roll_2 else None,
        "is_double": turn.is_double,
    }