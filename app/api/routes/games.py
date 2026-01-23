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

    # Get the current player from the most recent turn
    latest_turn = (
        session.query(models.Turn)
        .filter_by(game_id=game_id)
        .order_by(models.Turn.turn_number.desc())
        .first()
    )

    # Determine next player based on turn order
    current_player_id = None
    if latest_turn:
        current_player = session.query(models.GamePlayer).filter_by(
            game_player_id=latest_turn.active_game_player_id
        ).first()
        if current_player:
            # Find next player in turn order
            next_turn_order = (current_player.turn_order % len(players)) + 1
            next_player = next(p for p in players if p.turn_order == next_turn_order)
            current_player_id = next_player.game_player_id
    else:
        # No turns yet, current player is the first one
        if players:
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