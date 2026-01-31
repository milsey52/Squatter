"""Lobby API routes for game creation and joining."""
import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.api import deps, auth
from app.utils.game_code import generate_game_code
from app.api.routes import events


router = APIRouter()


# Request/Response Models
class CreateGameRequest(BaseModel):
    host_user_name: str
    max_players: int = 6
    house_rules: dict = {}


class JoinGameRequest(BaseModel):
    player_name: str


class SetReadyRequest(BaseModel):
    ready: bool


class GameCreatedResponse(BaseModel):
    game_id: int
    game_code: str
    session_token: str
    host_user_id: int


class GameJoinedResponse(BaseModel):
    game_id: int
    game_code: str
    session_token: str
    user_id: int
    status: str
    current_players: list


@router.post("/create", response_model=GameCreatedResponse)
def create_game(
    request: CreateGameRequest,
    session: Session = Depends(deps.get_session)
):
    """
    Create a new game and return game code and session token.

    The host automatically joins the game as the first player.
    """
    # Create or get user
    user = session.query(models.User).filter_by(
        display_name=request.host_user_name
    ).first()

    if not user:
        user = models.User(
            display_name=request.host_user_name,
            email=f"{request.host_user_name.lower().replace(' ', '_')}@monopoly.local"
        )
        session.add(user)
        session.flush()

    # Generate unique game code
    game_code = generate_game_code(session)

    # Create game
    game = models.Game(
        host_user_id=user.user_id,
        game_code=game_code,
        status="lobby",
        max_players=request.max_players
    )
    session.add(game)
    session.flush()

    # Create house rules
    house_rules_data = request.house_rules or {}
    house_rule = models.HouseRule(
        game_id=game.game_id,
        starting_cash=house_rules_data.get("starting_cash", 20000),
        pass_start_bonus=house_rules_data.get("pass_start_bonus", 2000),
        jackpot_enabled=house_rules_data.get("jackpot_enabled", True),
        allow_auctions=house_rules_data.get("allow_auctions", True),
        allow_trading=house_rules_data.get("allow_trading", True),
        notes=house_rules_data.get("notes")
    )
    session.add(house_rule)

    # Add host as first player
    game_player = models.GamePlayer(
        game_id=game.game_id,
        user_id=user.user_id,
        player_name=request.host_user_name,
        turn_order=1,
        is_ready=False
    )
    session.add(game_player)
    session.flush()

    # Create session token (7 day expiry)
    session_token = str(uuid.uuid4())
    game_session = models.GameSession(
        session_token=session_token,
        user_id=user.user_id,
        game_id=game.game_id,
        expires_at=datetime.now() + timedelta(days=7)
    )
    session.add(game_session)

    session.commit()

    return GameCreatedResponse(
        game_id=game.game_id,
        game_code=game_code,
        session_token=session_token,
        host_user_id=user.user_id
    )


@router.post("/join/{game_code}", response_model=GameJoinedResponse)
async def join_game(
    game_code: str,
    request: JoinGameRequest,
    session: Session = Depends(deps.get_session)
):
    """
    Join an existing game using the game code.

    Returns session token for the new player.
    """
    # Find game by code
    game = session.query(models.Game).filter_by(game_code=game_code.upper()).first()

    if not game:
        raise HTTPException(status_code=404, detail=f"Game with code '{game_code}' not found")

    # Check if game is full
    current_player_count = session.query(models.GamePlayer).filter_by(
        game_id=game.game_id
    ).count()

    if current_player_count >= game.max_players:
        raise HTTPException(
            status_code=400,
            detail=f"Game is full ({game.max_players} players maximum)"
        )

    # Check if game has already started
    if game.status not in ["lobby", "in_progress"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot join game with status '{game.status}'"
        )

    # Create or get user
    user = session.query(models.User).filter_by(
        display_name=request.player_name
    ).first()

    if not user:
        user = models.User(
            display_name=request.player_name,
            email=f"{request.player_name.lower().replace(' ', '_')}@monopoly.local"
        )
        session.add(user)
        session.flush()

    # Check if user already in this game
    existing_player = session.query(models.GamePlayer).filter_by(
        game_id=game.game_id,
        user_id=user.user_id
    ).first()

    if existing_player:
        # User re-joining, just create new session token
        session_token = str(uuid.uuid4())
        game_session = models.GameSession(
            session_token=session_token,
            user_id=user.user_id,
            game_id=game.game_id,
            expires_at=datetime.now() + timedelta(days=7)
        )
        session.add(game_session)
        session.commit()

        # Get current players
        players = session.query(models.GamePlayer).filter_by(
            game_id=game.game_id
        ).order_by(models.GamePlayer.turn_order).all()

        return GameJoinedResponse(
            game_id=game.game_id,
            game_code=game.game_code,
            session_token=session_token,
            user_id=user.user_id,
            status=game.status,
            current_players=[{
                "user_id": p.user_id,
                "player_name": p.player_name,
                "is_ready": p.is_ready
            } for p in players]
        )

    # Add new player
    next_turn_order = current_player_count + 1
    game_player = models.GamePlayer(
        game_id=game.game_id,
        user_id=user.user_id,
        player_name=request.player_name,
        turn_order=next_turn_order,
        is_ready=False
    )
    session.add(game_player)
    session.flush()

    # Create session token
    session_token = str(uuid.uuid4())
    game_session = models.GameSession(
        session_token=session_token,
        user_id=user.user_id,
        game_id=game.game_id,
        expires_at=datetime.now() + timedelta(days=7)
    )
    session.add(game_session)

    session.commit()

    # Broadcast player_joined event
    import asyncio
    await events.broadcast_game_event(
        game.game_id,
        "player_joined",
        {
            "user_id": user.user_id,
            "player_name": request.player_name,
            "turn_order": next_turn_order
        }
    )

    # Get current players
    players = session.query(models.GamePlayer).filter_by(
        game_id=game.game_id
    ).order_by(models.GamePlayer.turn_order).all()

    return GameJoinedResponse(
        game_id=game.game_id,
        game_code=game.game_code,
        session_token=session_token,
        user_id=user.user_id,
        status=game.status,
        current_players=[{
            "user_id": p.user_id,
            "player_name": p.player_name,
            "is_ready": p.is_ready
        } for p in players]
    )


@router.get("/{game_id}/lobby")
def get_lobby_status(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """
    Get current lobby status including all players and their ready state.

    Requires authentication.
    """
    user_id, token_game_id = auth_data

    # Verify the token's game_id matches the requested game_id
    if token_game_id != game_id:
        raise HTTPException(
            status_code=403,
            detail="Session token is for a different game"
        )

    game = deps.get_game_or_404(game_id, session)

    # Get all players
    players = session.query(models.GamePlayer).filter_by(
        game_id=game_id
    ).order_by(models.GamePlayer.turn_order).all()

    return {
        "game_code": game.game_code,
        "status": game.status,
        "host_user_id": game.host_user_id,
        "max_players": game.max_players,
        "players": [{
            "user_id": p.user_id,
            "player_name": p.player_name,
            "is_ready": p.is_ready,
            "turn_order": p.turn_order
        } for p in players]
    }


@router.post("/{game_id}/lobby/ready")
async def set_ready_status(
    game_id: int,
    request: SetReadyRequest,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """
    Set the current player's ready status in the lobby.

    Requires authentication.
    """
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(
            status_code=403,
            detail="Session token is for a different game"
        )

    game = deps.get_game_or_404(game_id, session)

    if game.status != "lobby":
        raise HTTPException(
            status_code=400,
            detail=f"Game is not in lobby (current status: {game.status})"
        )

    # Find player
    player = session.query(models.GamePlayer).filter_by(
        game_id=game_id,
        user_id=user_id
    ).first()

    if not player:
        raise HTTPException(
            status_code=404,
            detail="Player not found in this game"
        )

    player.is_ready = request.ready
    session.commit()

    # Broadcast player_ready event
    import asyncio
    await events.broadcast_game_event(
        game_id,
        "player_ready",
        {
            "user_id": user_id,
            "player_name": player.player_name,
            "is_ready": player.is_ready
        }
    )

    return {"success": True, "is_ready": player.is_ready}


@router.post("/{game_id}/lobby/start")
async def start_game(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """
    Start the game from lobby.

    Only the host can start the game, and all players must be ready.
    Initializes asset states for all properties.
    """
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(
            status_code=403,
            detail="Session token is for a different game"
        )

    game = deps.get_game_or_404(game_id, session)

    # Verify user is host
    if game.host_user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="Only the host can start the game"
        )

    if game.status != "lobby":
        raise HTTPException(
            status_code=400,
            detail=f"Game is not in lobby (current status: {game.status})"
        )

    # Check all players are ready
    players = session.query(models.GamePlayer).filter_by(game_id=game_id).all()

    if not players:
        raise HTTPException(
            status_code=400,
            detail="Cannot start game with no players"
        )

    not_ready = [p for p in players if not p.is_ready]
    if not_ready:
        raise HTTPException(
            status_code=400,
            detail=f"{len(not_ready)} player(s) are not ready"
        )

    # Initialize asset states (all unowned)
    assets = session.query(models.Asset).all()
    for asset in assets:
        # Check if asset state already exists
        existing = session.query(models.AssetState).filter_by(
            game_id=game_id,
            asset_id=asset.asset_id
        ).first()

        if not existing:
            asset_state = models.AssetState(
                game_id=game_id,
                asset_id=asset.asset_id,
                owner_game_player_id=None,
                is_mortgaged=False,
                improvement_level=0,
                has_hotel=False
            )
            session.add(asset_state)

    # Update game status
    game.status = "in_progress"

    # Set first player as current
    first_player = session.query(models.GamePlayer).filter_by(
        game_id=game_id,
        turn_order=1
    ).first()

    if first_player:
        game.current_game_player_id = first_player.game_player_id

    session.commit()

    # Broadcast game_started event
    import asyncio
    await events.broadcast_game_event(
        game_id,
        "game_started",
        {
            "status": "in_progress",
            "current_player_id": first_player.game_player_id if first_player else None
        }
    )

    return {
        "success": True,
        "status": "in_progress",
        "message": "Game started!"
    }


@router.get("/session/validate")
def validate_session(
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """
    Validate the current session token and return user and game info.

    Requires authentication via Authorization header.
    """
    user_id, game_id = auth_data

    game = deps.get_game_or_404(game_id, session)
    user = session.query(models.User).filter_by(user_id=user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "valid": True,
        "user_id": user_id,
        "game_id": game_id,
        "game_code": game.game_code,
        "game_status": game.status,
        "is_host": game.host_user_id == user_id,
        "display_name": user.display_name
    }
