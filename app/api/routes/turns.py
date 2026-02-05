from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.services.turn_manager import TurnManager
from app.services.decision_service import DecisionService
from app.api import deps, auth
from app import models
from app.api.routes import events
import asyncio

router = APIRouter()

@router.post("")
async def play_turn(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    user_id, token_game_id = auth_data

    # Verify the token's game_id matches the requested game_id
    if token_game_id != game_id:
        raise HTTPException(
            status_code=403,
            detail="Session token is for a different game"
        )

    # Verify game exists
    game = deps.get_game_or_404(game_id, session)

    # Find the game_player_id for the authenticated user
    current_user_player = session.query(models.GamePlayer).filter_by(
        game_id=game_id,
        user_id=user_id
    ).first()

    if not current_user_player:
        raise HTTPException(
            status_code=403,
            detail="You are not a player in this game"
        )

    # Verify this user is the current player
    if game.current_game_player_id != current_user_player.game_player_id:
        raise HTTPException(
            status_code=403,
            detail="It is not your turn"
        )

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
    pending_action = decision_service.get_auction_state()

    # Broadcast turn_played event
    await events.broadcast_game_event(
        game_id,
        "turn_played",
        {
            "turn_number": turn.turn_number,
            "player_id": turn.active_game_player_id,
            "dice_roll": [turn.dice_roll_1, turn.dice_roll_2],
            "is_double": turn.is_double,
            "has_pending_action": pending_action is not None
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

@router.post("/jail/pay-fine")
async def pay_jail_fine(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """
    Player pays $500 fine to get out of jail immediately before rolling.
    """
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    game = deps.get_game_or_404(game_id, session)

    if game.status == "suspended":
        raise HTTPException(status_code=400, detail="Game is suspended")

    # Find player
    player = session.query(models.GamePlayer).filter_by(
        game_id=game_id,
        user_id=user_id
    ).first()

    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # Verify it's their turn
    if game.current_game_player_id != player.game_player_id:
        raise HTTPException(status_code=400, detail="Not your turn")

    # Verify they're in jail
    if not player.in_jail:
        raise HTTPException(status_code=400, detail="You are not in jail")

    # Get current turn
    turn = session.query(models.Turn).filter_by(
        game_id=game_id,
        active_game_player_id=player.game_player_id
    ).order_by(models.Turn.turn_id.desc()).first()

    if not turn:
        raise HTTPException(status_code=400, detail="No active turn found")

    # Check if they have enough money
    from app.services.ledger_service import LedgerService
    ledger = LedgerService(session, game_id)
    balance = ledger.player_balance(player.game_player_id)

    from app.constants import JAIL_FINE
    if balance < JAIL_FINE:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient funds. Need ${JAIL_FINE}, have ${balance}"
        )

    # Pay fine and release from jail
    ledger.record_bank_payment(player, JAIL_FINE, "jail_fine", turn.turn_id)
    player.in_jail = False
    player.jail_turns = 0

    session.commit()

    # Broadcast event
    from app.api.routes import events
    await events.broadcast_game_event(
        game_id,
        "jail_fine_paid",
        {
            "player_id": player.game_player_id,
            "player_name": player.player_name,
            "amount": JAIL_FINE
        }
    )

    return {
        "success": True,
        "message": f"Paid ${JAIL_FINE} fine and released from jail",
        "in_jail": False
    }


@router.post("/jail/use-card")
async def use_jail_card(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """
    Player uses "Get Out of Jail Free" card to get out of jail.
    """
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    game = deps.get_game_or_404(game_id, session)

    if game.status == "suspended":
        raise HTTPException(status_code=400, detail="Game is suspended")

    # Find player
    player = session.query(models.GamePlayer).filter_by(
        game_id=game_id,
        user_id=user_id
    ).first()

    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # Verify it's their turn
    if game.current_game_player_id != player.game_player_id:
        raise HTTPException(status_code=400, detail="Not your turn")

    # Verify they're in jail
    if not player.in_jail:
        raise HTTPException(status_code=400, detail="You are not in jail")

    # Check if they have the card
    card_draw = (
        session.query(models.CardDraw)
        .join(models.Card)
        .filter(
            models.CardDraw.game_id == game_id,
            models.CardDraw.kept_by_player_id == player.game_player_id,
            models.Card.effect_code == "GET_OUT_OF_JAIL",
            models.CardDraw.discarded_at.is_(None),
        )
        .first()
    )

    if not card_draw:
        raise HTTPException(status_code=400, detail="You don't have a 'Get Out of Jail Free' card")

    # Use the card
    from datetime import datetime
    card_draw.discarded_at = datetime.now()
    
    # Release from jail
    player.in_jail = False
    player.jail_turns = 0

    session.commit()

    # Broadcast event
    from app.api.routes import events
    await events.broadcast_game_event(
        game_id,
        "jail_card_used",
        {
            "player_id": player.game_player_id,
            "player_name": player.player_name
        }
    )

    return {
        "success": True,
        "message": "Used 'Get Out of Jail Free' card and released from jail",
        "in_jail": False
    }


@router.get("/jail/status")
def get_jail_status(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """
    Get jail status for current player.
    """
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    game = deps.get_game_or_404(game_id, session)

    # Find player
    player = session.query(models.GamePlayer).filter_by(
        game_id=game_id,
        user_id=user_id
    ).first()

    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # Check for "Get Out of Jail Free" card
    has_jail_card = (
        session.query(models.CardDraw)
        .join(models.Card)
        .filter(
            models.CardDraw.game_id == game_id,
            models.CardDraw.kept_by_player_id == player.game_player_id,
            models.Card.effect_code == "GET_OUT_OF_JAIL",
            models.CardDraw.discarded_at.is_(None),
        )
        .first()
    ) is not None

    # Get balance
    from app.services.ledger_service import LedgerService
    ledger = LedgerService(session, game_id)
    balance = ledger.player_balance(player.game_player_id)

    from app.constants import JAIL_FINE
    can_afford_fine = balance >= JAIL_FINE

    return {
        "in_jail": player.in_jail,
        "jail_turns": player.jail_turns,
        "has_jail_card": has_jail_card,
        "can_afford_fine": can_afford_fine,
        "balance": balance,
        "jail_fine": JAIL_FINE,
        "turns_remaining": 3 - player.jail_turns if player.in_jail else 0
    }
