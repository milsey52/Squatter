"""Lobby API routes for game creation and joining."""
import hmac
import secrets
import uuid
from datetime import timedelta
from app.utils.time import utc_now
from typing import Optional
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
    game_rules: dict = {}


class JoinGameRequest(BaseModel):
    player_name: str
    # Required only when rejoining as an existing player in the game.
    rejoin_code: Optional[str] = None


class SetReadyRequest(BaseModel):
    ready: bool


class AddAIRequest(BaseModel):
    player_name: str
    difficulty: str  # 'easy' | 'medium' | 'hard'


class AIReactionTimeRequest(BaseModel):
    seconds: int  # 1-10


class StartingCashRequest(BaseModel):
    amount: int  # 1000-3000, multiple of 500


class GameCreatedResponse(BaseModel):
    game_id: int
    game_code: str
    session_token: str
    host_user_id: int
    rejoin_code: str


class GameJoinedResponse(BaseModel):
    game_id: int
    game_code: str
    session_token: str
    user_id: int
    status: str
    current_players: list
    rejoin_code: Optional[str] = None


def _new_rejoin_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _new_session(session: Session, user_id: int, game_id: int) -> str:
    # Opportunistic hygiene: every rejoin mints a fresh token, so without
    # cleanup the table grows forever. Sweep expired rows on each mint.
    session.query(models.GameSession).filter(
        models.GameSession.expires_at < utc_now()
    ).delete(synchronize_session=False)
    token = str(uuid.uuid4())
    session.add(models.GameSession(
        session_token=token,
        user_id=user_id,
        game_id=game_id,
        expires_at=utc_now() + timedelta(days=7),
    ))
    return token


@router.post("/create", response_model=GameCreatedResponse)
def create_game(
    request: CreateGameRequest,
    session: Session = Depends(deps.get_session)
):
    """Create a new game and return game code and session token."""
    host_name = request.host_user_name.strip()
    if not host_name:
        raise HTTPException(status_code=400, detail="host_user_name is required")

    # Users are per-game identities — always create a fresh row rather than
    # matching on display name, so a name is never a credential.
    user = models.User(display_name=host_name)
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

    # Create game rules
    rules_data = request.game_rules or {}
    from app.constants import DEFAULT_STARTING_CASH
    game_rule = models.GameRule(
        game_id=game.game_id,
        starting_cash=rules_data.get("starting_cash", DEFAULT_STARTING_CASH),
        quick_game=rules_data.get("quick_game", False),
        starting_paddock_type=rules_data.get("starting_paddock_type", "natural"),
        allow_trading=rules_data.get("allow_trading", True),
        notes=rules_data.get("notes")
    )
    session.add(game_rule)

    # Add host as first player
    rejoin_code = _new_rejoin_code()
    game_player = models.GamePlayer(
        game_id=game.game_id,
        user_id=user.user_id,
        player_name=host_name,
        turn_order=1,
        current_board_index=0,
        is_ready=False,
        rejoin_code=rejoin_code,
    )
    session.add(game_player)
    session.flush()

    # Create session token (7 day expiry)
    session_token = _new_session(session, user.user_id, game.game_id)

    session.commit()

    return GameCreatedResponse(
        game_id=game.game_id,
        game_code=game_code,
        session_token=session_token,
        host_user_id=user.user_id,
        rejoin_code=rejoin_code,
    )


@router.post("/join/{game_code}", response_model=GameJoinedResponse)
async def join_game(
    game_code: str,
    request: JoinGameRequest,
    session: Session = Depends(deps.get_session)
):
    """Join an existing game using the game code."""
    game = session.query(models.Game).filter_by(game_code=game_code.upper()).first()

    if not game:
        raise HTTPException(status_code=404, detail=f"Game with code '{game_code}' not found")

    if game.status not in ["lobby", "in_progress", "suspended", "rolling_for_order"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot join game with status '{game.status}'"
        )

    name = request.player_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="player_name is required")

    # Identity within a game is the player row, matched case-insensitively.
    existing_player = session.query(models.GamePlayer).filter(
        models.GamePlayer.game_id == game.game_id,
        func.lower(models.GamePlayer.player_name) == name.lower(),
    ).first()

    if existing_player:
        # Rejoining an existing seat requires that player's rejoin code —
        # a name alone is not a credential. AI seats and legacy rows
        # without a code can never be claimed by name.
        supplied = (request.rejoin_code or "").strip()
        if (existing_player.is_ai
                or not existing_player.rejoin_code
                or not supplied
                or not hmac.compare_digest(existing_player.rejoin_code, supplied)):
            raise HTTPException(
                status_code=403,
                detail=f"'{name}' is already a player in this game. "
                       "To rejoin as them, enter the rejoin code issued when they first joined."
            )

        existing_player.logged_in = True
        session_token = _new_session(session, existing_player.user_id, game.game_id)

        all_players = session.query(models.GamePlayer).filter_by(game_id=game.game_id).all()
        all_logged_in = all(p.logged_in for p in all_players)

        if game.status == "suspended" and all_logged_in:
            game.status = "in_progress"

        session.commit()

        players = session.query(models.GamePlayer).filter_by(
            game_id=game.game_id
        ).order_by(models.GamePlayer.turn_order).all()

        return GameJoinedResponse(
            game_id=game.game_id,
            game_code=game.game_code,
            session_token=session_token,
            user_id=existing_player.user_id,
            status=game.status,
            current_players=[{
                "user_id": p.user_id,
                "player_name": p.player_name,
                "is_ready": p.is_ready
            } for p in players],
            rejoin_code=existing_player.rejoin_code,
        )

    # New players can only join during lobby phase
    if game.status != "lobby":
        raise HTTPException(
            status_code=400,
            detail="Game has already started. Only existing players can re-join."
        )

    # Check if game is full
    current_player_count = session.query(models.GamePlayer).filter_by(
        game_id=game.game_id
    ).count()

    if current_player_count >= game.max_players:
        raise HTTPException(
            status_code=400,
            detail=f"Game is full ({game.max_players} players maximum)"
        )

    # Fresh per-game user for the new player (a name is never a credential).
    user = models.User(display_name=name)
    session.add(user)
    session.flush()

    # Add new player
    next_turn_order = current_player_count + 1
    rejoin_code = _new_rejoin_code()
    game_player = models.GamePlayer(
        game_id=game.game_id,
        user_id=user.user_id,
        player_name=name,
        turn_order=next_turn_order,
        current_board_index=0,
        is_ready=False,
        rejoin_code=rejoin_code,
    )
    session.add(game_player)
    session.flush()

    # Create session token
    session_token = _new_session(session, user.user_id, game.game_id)

    session.commit()

    # Broadcast player_joined event
    await events.broadcast_game_event(
        game.game_id,
        "player_joined",
        {
            "user_id": user.user_id,
            "player_name": name,
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
        } for p in players],
        rejoin_code=rejoin_code,
    )


@router.get("/{game_id}/lobby")
def get_lobby_status(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Get current lobby status."""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    game = deps.get_game_or_404(game_id, session)

    players = session.query(models.GamePlayer).filter_by(
        game_id=game_id
    ).order_by(models.GamePlayer.turn_order).all()

    me = next((p for p in players if p.user_id == user_id), None)

    return {
        "game_code": game.game_code,
        "status": game.status,
        "host_user_id": game.host_user_id,
        "max_players": game.max_players,
        # The requesting player's own rejoin code — never anyone else's.
        "your_rejoin_code": me.rejoin_code if me else None,
        "players": [{
            "game_player_id": p.game_player_id,
            "user_id": p.user_id,
            "player_name": p.player_name,
            "is_ready": p.is_ready,
            "turn_order": p.turn_order,
            "is_ai": bool(p.is_ai),
            "ai_difficulty": p.ai_difficulty,
        } for p in players]
    }


@router.post("/{game_id}/lobby/ready")
async def set_ready_status(
    game_id: int,
    request: SetReadyRequest,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Set the current player's ready status in the lobby."""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    game = deps.get_game_or_404(game_id, session)

    if game.status != "lobby":
        raise HTTPException(status_code=400, detail=f"Game is not in lobby (current status: {game.status})")

    player = session.query(models.GamePlayer).filter_by(
        game_id=game_id, user_id=user_id
    ).first()

    if not player:
        raise HTTPException(status_code=404, detail="Player not found in this game")

    player.is_ready = request.ready
    session.commit()

    await events.broadcast_game_event(
        game_id, "player_ready",
        {"user_id": user_id, "player_name": player.player_name, "is_ready": player.is_ready}
    )

    return {"success": True, "is_ready": player.is_ready}


@router.post("/{game_id}/settings/ai-reaction-time")
async def set_ai_reaction_time(
    game_id: int,
    request: AIReactionTimeRequest,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Host adjusts how long an AI-owned modal lingers before the AI
    dismisses it (1-10 seconds). Stored on game_rules so the autopilot
    picks it up per-game."""
    user_id, token_game_id = auth_data
    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")
    game = deps.get_game_or_404(game_id, session)
    if game.host_user_id != user_id:
        raise HTTPException(status_code=403, detail="Only the host can change this setting")

    seconds = int(request.seconds)
    if seconds < 1 or seconds > 10:
        raise HTTPException(status_code=400, detail="seconds must be between 1 and 10")

    rules = session.query(models.GameRule).filter_by(game_id=game_id).first()
    if rules is None:
        raise HTTPException(status_code=404, detail="Game rules not found")
    rules.ai_reaction_time_seconds = seconds
    session.commit()

    await events.broadcast_game_event(
        game_id, "game_state_changed",
        {"reason": "ai_reaction_time_updated", "seconds": seconds}
    )
    return {"success": True, "seconds": seconds}


@router.post("/{game_id}/settings/starting-cash")
async def set_starting_cash(
    game_id: int,
    request: StartingCashRequest,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Host sets the opening kitty per player ($1000-$3000 in $500
    increments). Only adjustable while the game is still in the lobby
    — once dice have been rolled the kitty is locked in."""
    user_id, token_game_id = auth_data
    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")
    game = deps.get_game_or_404(game_id, session)
    if game.host_user_id != user_id:
        raise HTTPException(status_code=403, detail="Only the host can change this setting")
    if game.status != "lobby":
        raise HTTPException(status_code=400,
                            detail="Opening kitty can only be changed before the game starts")

    amount = int(request.amount)
    if amount < 1000 or amount > 3000 or amount % 500 != 0:
        raise HTTPException(status_code=400,
                            detail="amount must be between $1000 and $3000 in $500 increments")

    rules = session.query(models.GameRule).filter_by(game_id=game_id).first()
    if rules is None:
        raise HTTPException(status_code=404, detail="Game rules not found")
    rules.starting_cash = amount
    session.commit()

    await events.broadcast_game_event(
        game_id, "game_state_changed",
        {"reason": "starting_cash_updated", "amount": amount}
    )
    return {"success": True, "amount": amount}


@router.post("/{game_id}/lobby/add-ai")
async def add_ai_player(
    game_id: int,
    request: AddAIRequest,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Host adds an AI player to the lobby. AI players have no user_id,
    auto-ready, and are driven by the server-side autopilot during play."""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    game = deps.get_game_or_404(game_id, session)

    if game.host_user_id != user_id:
        raise HTTPException(status_code=403, detail="Only the host can add AI players")

    if game.status != "lobby":
        raise HTTPException(status_code=400, detail=f"Cannot add AI player while game status is {game.status}")

    difficulty = (request.difficulty or "").lower()
    if difficulty not in ("easy", "medium", "hard"):
        raise HTTPException(status_code=400, detail="difficulty must be one of: easy, medium, hard")

    name = request.player_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="player_name is required")

    # Reject duplicate names within the game (humans included)
    existing_name = session.query(models.GamePlayer).filter_by(
        game_id=game_id, player_name=name
    ).first()
    if existing_name:
        raise HTTPException(status_code=400, detail=f"A player named '{name}' is already in this game")

    current_count = session.query(models.GamePlayer).filter_by(game_id=game_id).count()
    if current_count >= game.max_players:
        raise HTTPException(status_code=400, detail=f"Game is full ({game.max_players} players maximum)")

    next_turn_order = current_count + 1
    ai_player = models.GamePlayer(
        game_id=game_id,
        user_id=None,
        player_name=name,
        turn_order=next_turn_order,
        current_board_index=0,
        is_ready=True,         # auto-ready
        logged_in=True,        # always "logged in" so they don't suspend the game
        is_ai=True,
        ai_difficulty=difficulty,
    )
    session.add(ai_player)
    session.commit()

    await events.broadcast_game_event(
        game_id, "player_joined",
        {
            "user_id": None,
            "player_name": name,
            "turn_order": next_turn_order,
            "is_ai": True,
            "ai_difficulty": difficulty,
        }
    )

    return {
        "success": True,
        "game_player_id": ai_player.game_player_id,
        "player_name": name,
        "difficulty": difficulty,
    }


@router.post("/{game_id}/lobby/start")
async def start_game(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Start the game from lobby. Initializes stations for all players."""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    game = deps.get_game_or_404(game_id, session)

    if game.host_user_id != user_id:
        raise HTTPException(status_code=403, detail="Only the host can start the game")

    if game.status != "lobby":
        raise HTTPException(status_code=400, detail=f"Game is not in lobby (current status: {game.status})")

    players = session.query(models.GamePlayer).filter_by(game_id=game_id).all()

    if not players:
        raise HTTPException(status_code=400, detail="Cannot start game with no players")

    not_ready = [p for p in players if not p.is_ready]
    if not_ready:
        raise HTTPException(status_code=400, detail=f"{len(not_ready)} player(s) are not ready")

    # Initialize game state (paddocks and stud rams)
    from app.services.game_service import initialize_game_state
    rules = session.query(models.GameRule).filter_by(game_id=game_id).first()
    quick_game = rules.quick_game if rules else False
    initialize_game_state(session, game_id, quick_game=quick_game)

    # Update game status to rolling_for_order
    game.status = "rolling_for_order"

    session.commit()

    await events.broadcast_game_event(
        game_id, "turn_order_rolling_started",
        {"status": "rolling_for_order", "player_count": len(players)}
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
    """Validate the current session token."""
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
    """Player rolls dice to determine turn order."""
    import random

    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    game = deps.get_game_or_404(game_id, session)

    if game.status != "rolling_for_order":
        raise HTTPException(status_code=400, detail=f"Game is not in rolling_for_order state (current: {game.status})")

    player = session.query(models.GamePlayer).filter_by(
        game_id=game_id, user_id=user_id
    ).first()

    if not player:
        raise HTTPException(status_code=404, detail="Player not found in this game")

    # Active round comes from games.current_turn_order_round (advanced by /start-reroll)
    current_round = game.current_turn_order_round or 1

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

    await events.broadcast_game_event(
        game_id, "turn_order_roll",
        {
            "player_id": player.game_player_id,
            "player_name": player.player_name,
            "dice1": dice1, "dice2": dice2, "total": total,
            "round": current_round
        }
    )

    return {"success": True, "dice1": dice1, "dice2": dice2, "total": total, "round": current_round}


@router.get("/{game_id}/turn-order/rolls")
def get_turn_order_rolls(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Get current turn order rolls for all players."""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    game = deps.get_game_or_404(game_id, session)

    players = session.query(models.GamePlayer).filter_by(game_id=game_id).all()

    current_round = game.current_turn_order_round or 1

    rolls_query = (
        session.query(models.TurnOrderRoll)
        .filter(
            models.TurnOrderRoll.game_id == game_id,
            models.TurnOrderRoll.round_number == current_round
        )
        .all()
    )

    rolls_map = {r.game_player_id: r for r in rolls_query}

    roll_data = []
    for player in players:
        roll = rolls_map.get(player.game_player_id)
        roll_data.append({
            "game_player_id": player.game_player_id,
            "user_id": player.user_id,
            "player_name": player.player_name,
            "dice1": roll.dice_roll_1 if roll else None,
            "dice2": roll.dice_roll_2 if roll else None,
            "total": roll.total if roll else None
        })

    all_rolled = len(rolls_query) == len(players)

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
            needs_reroll = True
            for w in winners:
                winner_player = session.query(models.GamePlayer).get(w.game_player_id)
                tied_players.append({
                    "game_player_id": w.game_player_id,
                    "player_name": winner_player.player_name,
                    "total": w.total
                })

    return {
        "round": current_round,
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
    """Start a new round of rolling for tied players."""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    game = deps.get_game_or_404(game_id, session)

    if game.host_user_id != user_id:
        raise HTTPException(status_code=403, detail="Only the host can start a reroll")

    if game.status != "rolling_for_order":
        raise HTTPException(status_code=400, detail="Game is not in rolling_for_order state")

    new_round = (game.current_turn_order_round or 1) + 1
    game.current_turn_order_round = new_round
    session.commit()

    await events.broadcast_game_event(
        game_id, "turn_order_reroll", {"round": new_round}
    )

    return {"success": True, "message": "Reroll started", "new_round": new_round}


@router.post("/{game_id}/turn-order/finalize")
async def finalize_turn_order(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Finalize turn order and start the game."""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    game = deps.get_game_or_404(game_id, session)

    if game.host_user_id != user_id:
        raise HTTPException(status_code=403, detail="Only the host can finalize turn order")

    if game.status != "rolling_for_order":
        raise HTTPException(status_code=400, detail="Game is not in rolling_for_order state")

    current_round = game.current_turn_order_round or 1

    rolls = (
        session.query(models.TurnOrderRoll)
        .filter(
            models.TurnOrderRoll.game_id == game_id,
            models.TurnOrderRoll.round_number == current_round
        )
        .all()
    )

    all_players = session.query(models.GamePlayer).filter_by(game_id=game_id).all()

    if not rolls or len(rolls) != len(all_players):
        raise HTTPException(status_code=400, detail="Not all players have rolled yet")

    max_total = max(r.total for r in rolls)
    winners = [r for r in rolls if r.total == max_total]

    if len(winners) > 1:
        raise HTTPException(status_code=400, detail="There is a tie - players must reroll")

    winner_roll = winners[0]
    winner_player = session.query(models.GamePlayer).filter_by(
        game_player_id=winner_roll.game_player_id
    ).first()

    # Reorder players: winner gets turn_order=1
    players_sorted = sorted(all_players, key=lambda p: p.turn_order)
    other_players = [p for p in players_sorted if p.game_player_id != winner_player.game_player_id]
    new_order = [winner_player] + other_players

    # Two-step to avoid UNIQUE constraint violation
    for idx, player in enumerate(new_order, start=1):
        player.turn_order = idx + 1000
    session.flush()

    for idx, player in enumerate(new_order, start=1):
        player.turn_order = idx

    game.status = "in_progress"
    game.current_game_player_id = winner_player.game_player_id

    session.commit()

    await events.broadcast_game_event(
        game_id, "game_started",
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
    """Logout current player and suspend the game."""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    game = deps.get_game_or_404(game_id, session)

    player = session.query(models.GamePlayer).filter_by(
        game_id=game_id, user_id=user_id
    ).first()

    if not player:
        raise HTTPException(status_code=404, detail="Player not found in this game")

    player.logged_in = False

    if game.status in ["in_progress", "rolling_for_order"]:
        game.status = "suspended"

    session.commit()

    await events.broadcast_game_event(
        game_id, "player_logged_out",
        {
            "player_id": player.game_player_id,
            "player_name": player.player_name,
            "game_suspended": game.status == "suspended"
        }
    )

    return {"success": True, "message": "Logged out successfully", "game_suspended": game.status == "suspended"}


@router.post("/{game_id}/login")
async def login_player(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Login player and potentially resume the game."""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    game = deps.get_game_or_404(game_id, session)

    player = session.query(models.GamePlayer).filter_by(
        game_id=game_id, user_id=user_id
    ).first()

    if not player:
        raise HTTPException(status_code=404, detail="Player not found in this game")

    player.logged_in = True

    all_players = session.query(models.GamePlayer).filter_by(game_id=game_id).all()
    all_logged_in = all(p.logged_in for p in all_players)

    game_resumed = False
    if game.status == "suspended" and all_logged_in:
        has_turn_order_rolls = session.query(models.TurnOrderRoll).filter_by(game_id=game_id).first() is not None
        if has_turn_order_rolls and not game.current_game_player_id:
            game.status = "rolling_for_order"
        else:
            game.status = "in_progress"
        game_resumed = True

    session.commit()

    await events.broadcast_game_event(
        game_id, "player_logged_in",
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
    """Get login status of all players in the game."""
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
