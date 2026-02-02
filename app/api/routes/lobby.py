"""Lobby API routes for game creation and joining."""
import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

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

    # Check if game has already started
    if game.status not in ["lobby", "in_progress", "suspended", "rolling_for_order"]:
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
        # User re-joining, mark them as logged in and create new session token
        existing_player.logged_in = True

        session_token = str(uuid.uuid4())
        game_session = models.GameSession(
            session_token=session_token,
            user_id=user.user_id,
            game_id=game.game_id,
            expires_at=datetime.now() + timedelta(days=7)
        )
        session.add(game_session)

        # Check if all players are now logged in and resume game if needed
        all_players = session.query(models.GamePlayer).filter_by(game_id=game.game_id).all()
        all_logged_in = all(p.logged_in for p in all_players)

        if game.status == "suspended" and all_logged_in:
            # Resume the game
            game.status = "in_progress"

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

    # Check if game is full (only for NEW players)
    current_player_count = session.query(models.GamePlayer).filter_by(
        game_id=game.game_id
    ).count()

    if current_player_count >= game.max_players:
        raise HTTPException(
            status_code=400,
            detail=f"Game is full ({game.max_players} players maximum)"
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

    # Update game status to rolling_for_order
    game.status = "rolling_for_order"

    session.commit()

    # Broadcast game_started event
    import asyncio
    await events.broadcast_game_event(
        game_id,
        "turn_order_rolling_started",
        {
            "status": "rolling_for_order",
            "player_count": len(players)
        }
    )

    return {
        "success": True,
        "status": "rolling_for_order",
        "message": "Roll for turn order!"
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


@router.post("/{game_id}/turn-order/roll")
async def roll_for_turn_order(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """
    Player rolls dice to determine turn order.

    Each player must roll. If there's a tie for highest, those players roll again.
    """
    import random

    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    game = deps.get_game_or_404(game_id, session)

    if game.status != "rolling_for_order":
        raise HTTPException(
            status_code=400,
            detail=f"Game is not in rolling_for_order state (current: {game.status})"
        )

    # Find player
    player = session.query(models.GamePlayer).filter_by(
        game_id=game_id,
        user_id=user_id
    ).first()

    if not player:
        raise HTTPException(status_code=404, detail="Player not found in this game")

    # Determine current round number
    max_round = session.query(func.max(models.TurnOrderRoll.round_number)).filter_by(
        game_id=game_id
    ).scalar() or 0
    current_round = max_round if max_round > 0 else 1

    # Check if player has already rolled in this round
    existing_roll = session.query(models.TurnOrderRoll).filter_by(
        game_id=game_id,
        game_player_id=player.game_player_id,
        round_number=current_round
    ).first()

    if existing_roll:
        raise HTTPException(status_code=400, detail="You have already rolled in this round")

    # Roll dice
    dice1 = random.randint(1, 6)
    dice2 = random.randint(1, 6)
    total = dice1 + dice2

    # Record roll
    turn_order_roll = models.TurnOrderRoll(
        game_id=game_id,
        game_player_id=player.game_player_id,
        round_number=current_round,
        dice_roll_1=dice1,
        dice_roll_2=dice2,
        total=total
    )
    session.add(turn_order_roll)
    session.commit()

    # Broadcast roll event
    await events.broadcast_game_event(
        game_id,
        "turn_order_roll",
        {
            "player_id": player.game_player_id,
            "player_name": player.player_name,
            "dice1": dice1,
            "dice2": dice2,
            "total": total,
            "round": current_round
        }
    )

    return {
        "success": True,
        "dice1": dice1,
        "dice2": dice2,
        "total": total,
        "round": current_round
    }


@router.get("/{game_id}/turn-order/rolls")
def get_turn_order_rolls(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """
    Get current turn order rolls for all players.

    Returns rolls for the current round, winner info, and whether more rolls are needed.
    """
    from sqlalchemy import func

    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    game = deps.get_game_or_404(game_id, session)

    # Get all players
    players = session.query(models.GamePlayer).filter_by(game_id=game_id).all()

    # Get current round
    max_round = session.query(func.max(models.TurnOrderRoll.round_number)).filter_by(
        game_id=game_id
    ).scalar() or 1

    # Get rolls for current round
    rolls_query = (
        session.query(models.TurnOrderRoll)
        .filter(
            models.TurnOrderRoll.game_id == game_id,
            models.TurnOrderRoll.round_number == max_round
        )
        .all()
    )

    # Create a map of game_player_id -> roll
    rolls_map = {r.game_player_id: r for r in rolls_query}

    # Build roll data for ALL players (whether they've rolled or not)
    roll_data = []
    for player in players:
        roll = rolls_map.get(player.game_player_id)
        roll_data.append({
            "game_player_id": player.game_player_id,
            "player_name": player.player_name,
            "dice1": roll.dice_roll_1 if roll else None,
            "dice2": roll.dice_roll_2 if roll else None,
            "total": roll.total if roll else None
        })

    # Check if all players have rolled
    all_rolled = len(rolls_query) == len(players)

    # Determine winner and ties
    winner = None
    needs_reroll = False
    tied_players = []

    if all_rolled and rolls_query:
        max_total = max(r.total for r in rolls_query)
        winners = [r for r in rolls_query if r.total == max_total]

        if len(winners) == 1:
            winner_player = session.query(models.GamePlayer).get(winners[0].game_player_id)
            winner = {
                "game_player_id": winners[0].game_player_id,
                "player_name": winner_player.player_name,
                "total": winners[0].total
            }
        else:
            # Tie - need reroll
            needs_reroll = True
            for w in winners:
                winner_player = session.query(models.GamePlayer).get(w.game_player_id)
                tied_players.append({
                    "game_player_id": w.game_player_id,
                    "player_name": winner_player.player_name,
                    "total": w.total
                })

    return {
        "round": max_round,
        "rolls": roll_data,
        "all_rolled": all_rolled,
        "winner": winner,
        "needs_reroll": needs_reroll,
        "tied_players": tied_players,
        "total_players": len(players)
    }


@router.post("/{game_id}/turn-order/start-reroll")
async def start_reroll(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """
    Start a new round of rolling for tied players.

    Only host can initiate this.
    """
    from sqlalchemy import func

    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    game = deps.get_game_or_404(game_id, session)

    # Verify user is host
    if game.host_user_id != user_id:
        raise HTTPException(status_code=403, detail="Only the host can start a reroll")

    if game.status != "rolling_for_order":
        raise HTTPException(status_code=400, detail="Game is not in rolling_for_order state")

    # Get current round
    max_round = session.query(func.max(models.TurnOrderRoll.round_number)).filter_by(
        game_id=game_id
    ).scalar() or 1

    # Delete rolls for tied players to start new round
    # (Actually, we'll just increment the round number - tied players roll in the new round)

    session.commit()

    # Broadcast reroll event
    await events.broadcast_game_event(
        game_id,
        "turn_order_reroll",
        {"round": max_round + 1}
    )

    return {
        "success": True,
        "message": "Reroll started",
        "new_round": max_round + 1
    }


@router.post("/{game_id}/turn-order/finalize")
async def finalize_turn_order(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """
    Finalize turn order and start the game.

    Only host can do this, and there must be a clear winner.
    Sets winner as player 1, others maintain clockwise order.
    """
    from sqlalchemy import func

    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    game = deps.get_game_or_404(game_id, session)

    # Verify user is host
    if game.host_user_id != user_id:
        raise HTTPException(status_code=403, detail="Only the host can finalize turn order")

    if game.status != "rolling_for_order":
        raise HTTPException(status_code=400, detail="Game is not in rolling_for_order state")

    # Get current round
    max_round = session.query(func.max(models.TurnOrderRoll.round_number)).filter_by(
        game_id=game_id
    ).scalar()

    if not max_round:
        raise HTTPException(status_code=400, detail="No rolls have been made yet")

    # Get rolls for current round
    rolls = (
        session.query(models.TurnOrderRoll)
        .filter(
            models.TurnOrderRoll.game_id == game_id,
            models.TurnOrderRoll.round_number == max_round
        )
        .all()
    )

    # Get all players to verify all have rolled
    all_players = session.query(models.GamePlayer).filter_by(game_id=game_id).all()

    if len(rolls) != len(all_players):
        raise HTTPException(status_code=400, detail="Not all players have rolled yet")

    # Find winner
    max_total = max(r.total for r in rolls)
    winners = [r for r in rolls if r.total == max_total]

    if len(winners) > 1:
        raise HTTPException(
            status_code=400,
            detail="There is a tie - players must reroll"
        )

    winner_roll = winners[0]

    # Get winner and all players
    winner_player = session.query(models.GamePlayer).filter_by(
        game_player_id=winner_roll.game_player_id
    ).first()

    # Reorder players: winner gets turn_order=1, others follow in their original clockwise order
    # Get players sorted by their original turn_order
    players_sorted = sorted(all_players, key=lambda p: p.turn_order)

    # Move winner to front - filter out winner by game_player_id
    other_players = [p for p in players_sorted if p.game_player_id != winner_player.game_player_id]
    new_order = [winner_player] + other_players

    # Update turn orders in two steps to avoid UNIQUE constraint violation
    # First, set all to temporary high values
    for idx, player in enumerate(new_order, start=1):
        player.turn_order = idx + 1000  # Temporary high value
    session.flush()  # Apply temporary values

    # Then, set to final values
    for idx, player in enumerate(new_order, start=1):
        player.turn_order = idx

    # Update game status and set first player
    game.status = "in_progress"
    game.current_game_player_id = winner_player.game_player_id

    session.commit()

    # Broadcast game_started event
    await events.broadcast_game_event(
        game_id,
        "game_started",
        {
            "status": "in_progress",
            "current_player_id": winner_player.game_player_id,
            "winner_name": winner_player.player_name,
            "turn_order": [{"player_id": p.game_player_id, "player_name": p.player_name, "order": p.turn_order} for p in new_order]
        }
    )

    return {
        "success": True,
        "status": "in_progress",
        "winner": winner_player.player_name,
        "message": f"{winner_player.player_name} goes first!"
    }


@router.post("/{game_id}/logout")
async def logout_player(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """
    Logout current player and suspend the game.

    Game is automatically suspended when any player logs out.
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
        raise HTTPException(status_code=404, detail="Player not found in this game")

    # Mark player as logged out
    player.logged_in = False

    # Suspend game if it's in progress or rolling for turn order
    if game.status in ["in_progress", "rolling_for_order"]:
        game.status = "suspended"

    session.commit()

    # Broadcast player logout event
    await events.broadcast_game_event(
        game_id,
        "player_logged_out",
        {
            "player_id": player.game_player_id,
            "player_name": player.player_name,
            "game_suspended": game.status == "suspended"
        }
    )

    return {
        "success": True,
        "message": "Logged out successfully",
        "game_suspended": game.status == "suspended"
    }


@router.post("/{game_id}/login")
async def login_player(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """
    Login player and potentially resume the game.

    Game is automatically resumed when all players are logged back in.
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
        raise HTTPException(status_code=404, detail="Player not found in this game")

    # Mark player as logged in
    player.logged_in = True

    # Check if all players are now logged in
    all_players = session.query(models.GamePlayer).filter_by(game_id=game_id).all()
    all_logged_in = all(p.logged_in for p in all_players)

    # Resume game if suspended and all players are back
    game_resumed = False
    if game.status == "suspended" and all_logged_in:
        # Determine what status to resume to
        # Check if there are any turn order rolls - if so, resume to rolling_for_order
        has_turn_order_rolls = session.query(models.TurnOrderRoll).filter_by(game_id=game_id).first() is not None

        if has_turn_order_rolls and not game.current_game_player_id:
            game.status = "rolling_for_order"
        else:
            game.status = "in_progress"
        game_resumed = True

    session.commit()

    # Broadcast player login event
    await events.broadcast_game_event(
        game_id,
        "player_logged_in",
        {
            "player_id": player.game_player_id,
            "player_name": player.player_name,
            "all_logged_in": all_logged_in,
            "game_resumed": game_resumed,
            "game_status": game.status
        }
    )

    return {
        "success": True,
        "message": "Logged in successfully",
        "all_logged_in": all_logged_in,
        "game_resumed": game_resumed,
        "game_status": game.status
    }


@router.get("/{game_id}/player-status")
def get_player_status(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """
    Get login status of all players in the game.
    """
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    game = deps.get_game_or_404(game_id, session)

    players = session.query(models.GamePlayer).filter_by(game_id=game_id).all()

    return {
        "game_status": game.status,
        "players": [{
            "game_player_id": p.game_player_id,
            "player_name": p.player_name,
            "logged_in": p.logged_in
        } for p in players],
        "all_logged_in": all(p.logged_in for p in players),
        "logged_out_players": [p.player_name for p in players if not p.logged_in]
    }
