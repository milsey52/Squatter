from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_session 
from app import models
from app.api import deps
from app.schemas import CreateGameRequest
from app.services.seed import seed_asset_states
from app.services.ledger_service import LedgerService

router = APIRouter()

@router.post("/")
def create_game(payload: CreateGameRequest, session: Session = Depends(deps.get_session)):
    game = models.Game(...)
    session.add(game)
    session.flush()
    # add house rules, players...
    seed_asset_states(session, game.game_id)
    session.commit()
    return {"game_id": game.game_id}

@router.get("/{game_id}")
def get_game(game_id: int, session: Session = Depends(deps.get_session)):
    game = session.query(models.Game).filter_by(game_id=game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    players = (
        session.query(models.GamePlayer)
        .filter_by(game_id=game_id)
        .order_by(models.GamePlayer.turn_order)
        .all()
    )

    # Use the current_game_player_id stored in the game
    # This is set by TurnManager and is the source of truth
    current_player_id = game.current_game_player_id

    # If not set yet (brand new game), default to first player
    if not current_player_id and players:
        current_player_id = players[0].game_player_id

    return {
        "game_id": game.game_id,
        "status": game.status,
        "current_player_id": current_player_id,
        "house_rules": {
            "starting_cash": game.house_rules.starting_cash,
            "pass_start_bonus": game.house_rules.pass_start_bonus,
            "jackpot_enabled": game.house_rules.jackpot_enabled,
        },
        "players": [
            {
                "game_player_id": p.game_player_id,
                "user_id": p.user_id,
                "player_name": p.player_name,
                "current_space_id": p.current_space_id,
                "in_jail": p.in_jail,
                "turn_order": p.turn_order,
            }
            for p in players
        ],
    }

@router.get("/{game_id}/player_balances")
def player_balances(game_id: int, session: Session = Depends(get_session)):
    players = session.query(models.GamePlayer).filter_by(game_id=game_id).all()
    balances = {}
    for p in players:
        # LedgerService method
        balance = LedgerService(session, game_id).player_balance(p.game_player_id)
        balances[p.game_player_id] = balance
    return balances

@router.get("/{game_id}/dice_rolls")
def get_dice_rolls(game_id: int, session: Session = Depends(get_session)):
    """Get history of dice rolls for a game"""
    from sqlalchemy import alias

    game = session.query(models.Game).filter_by(game_id=game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    # Create aliases for the two space joins (from and to locations)
    space_from = alias(models.Space, name='space_from')
    space_to = alias(models.Space, name='space_to')

    # Query turns with movements to get from/to locations in a single query
    rolls = (
        session.query(
            models.Turn.turn_number,
            models.GamePlayer.player_name,
            models.Turn.dice_roll_1,
            models.Turn.dice_roll_2,
            space_from.c.space_id.label('from_location'),
            space_to.c.space_id.label('to_location')
        )
        .join(models.GamePlayer, models.Turn.active_game_player_id == models.GamePlayer.game_player_id)
        .outerjoin(
            models.Movement,
            (models.Turn.turn_id == models.Movement.turn_id) &
            (models.Movement.movement_type == 'roll')
        )
        .outerjoin(space_from, models.Movement.start_space_id == space_from.c.space_id)
        .outerjoin(space_to, models.Movement.end_space_id == space_to.c.space_id)
        .filter(models.Turn.game_id == game_id)
        .order_by(models.Turn.turn_number.desc())
        .limit(20)
        .all()
    )

    result = []
    for turn_number, player_name, dice1, dice2, from_location, to_location in rolls:
        result.append({
            "roll_number": turn_number,
            "player": player_name,
            "dice1": dice1,
            "dice2": dice2,
            "total": (dice1 or 0) + (dice2 or 0),
            "from_location": from_location,
            "to_location": to_location
        })

    return {"rolls": result}