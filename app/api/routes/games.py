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