# app/api/routes/turns.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.services.turn_manager import TurnManager
from app.services.decision_service import DecisionService
from app.api import deps, auth
from app import models
from app.api.routes import events

router = APIRouter()


@router.post("")
async def play_turn(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    game = deps.get_game_or_404(game_id, session)

    # Find the game_player_id for the authenticated user
    current_user_player = session.query(models.GamePlayer).filter_by(
        game_id=game_id,
        user_id=user_id
    ).first()

    if not current_user_player:
        raise HTTPException(status_code=403, detail="You are not a player in this game")

    # Verify this user is the current player
    if game.current_game_player_id != current_user_player.game_player_id:
        raise HTTPException(status_code=403, detail="It is not your turn")

    # Check if there's a pending action that must be resolved first
    decision_service = DecisionService(session, game_id)
    pending = decision_service.get_pending_action()
    if pending:
        raise HTTPException(
            status_code=400,
            detail="Cannot start new turn - pending action must be resolved first"
        )

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

    # Check if a pending action was created this turn
    pending_action = decision_service.get_pending_action_state()

    # Get updated player position
    updated_player = session.query(models.GamePlayer).filter_by(
        game_player_id=turn.active_game_player_id
    ).first()

    # Broadcast turn_played event
    await events.broadcast_game_event(
        game_id,
        "turn_played",
        {
            "turn_number": turn.turn_number,
            "player_id": turn.active_game_player_id,
            "dice_roll": [turn.dice_roll_1, turn.dice_roll_2],
            "is_double": turn.is_double,
            "new_position": updated_player.current_space_id if updated_player else None,
            "visiting_town_turns": updated_player.visiting_town_turns if updated_player else 0,
            "is_in_drought": updated_player.is_in_drought if updated_player else False,
            "has_pending_action": pending_action is not None,
            "pending_action": pending_action,
        }
    )

    return {
        "turn_number": turn.turn_number,
        "player_id": turn.active_game_player_id,
        "dice_roll_1": turn.dice_roll_1,
        "dice_roll_2": turn.dice_roll_2,
        "total_roll": turn.dice_roll_1 + turn.dice_roll_2 if turn.dice_roll_1 and turn.dice_roll_2 else None,
        "is_double": turn.is_double,
        "pending_action": pending_action,
    }
