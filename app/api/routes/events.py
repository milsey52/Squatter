"""Server-Sent Events (SSE) endpoint for real-time game updates."""
import asyncio
import json
from typing import Dict, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.api import deps, auth
from app import models
from app.utils.time import utc_now

router = APIRouter()

# Global event manager: game_id -> list of asyncio.Queues (one per connected client)
_game_event_queues: Dict[int, List[asyncio.Queue]] = {}


async def broadcast_game_event(game_id: int, event_type: str, data: dict):
    """
    Broadcast an event to all connected clients for a specific game.

    Args:
        game_id: The game to broadcast to
        event_type: Type of event (e.g., 'player_joined', 'turn_played')
        data: Event payload as dictionary
    """
    if game_id not in _game_event_queues:
        return

    event = {
        "type": event_type,
        "data": data
    }

    # Put event in all queues for this game
    dead_queues = []
    for queue in _game_event_queues[game_id]:
        try:
            # Use put_nowait to avoid blocking
            queue.put_nowait(event)
        except asyncio.QueueFull:
            # Queue is full, client is probably disconnected
            dead_queues.append(queue)

    # Clean up dead queues
    for queue in dead_queues:
        _game_event_queues[game_id].remove(queue)


async def event_generator(game_id: int, user_id: int):
    """
    Generate SSE events for a specific game and user.

    Args:
        game_id: The game to listen to
        user_id: The authenticated user (for future per-user events)

    Yields:
        SSE formatted events
    """
    # Create a queue for this connection
    queue = asyncio.Queue(maxsize=100)

    # Register this queue for the game
    if game_id not in _game_event_queues:
        _game_event_queues[game_id] = []
    _game_event_queues[game_id].append(queue)

    try:
        # Send initial connection confirmation
        yield {
            "event": "connected",
            "data": json.dumps({"game_id": game_id, "user_id": user_id})
        }

        # Stream events from the queue
        while True:
            # Wait for next event with timeout for heartbeat
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)

                # Send the event
                yield {
                    "event": event["type"],
                    "data": json.dumps(event["data"])
                }

            except asyncio.TimeoutError:
                # Send heartbeat to keep connection alive
                yield {
                    "event": "heartbeat",
                    "data": json.dumps({"timestamp": asyncio.get_event_loop().time()})
                }

    except asyncio.CancelledError:
        # Client disconnected
        pass
    finally:
        # Cleanup: remove this queue from the game
        if game_id in _game_event_queues:
            if queue in _game_event_queues[game_id]:
                _game_event_queues[game_id].remove(queue)

            # Remove game entry if no more clients
            if not _game_event_queues[game_id]:
                del _game_event_queues[game_id]


@router.get("/{game_id}/events")
async def game_events(
    game_id: int,
    token: str,  # Session token as query parameter (EventSource doesn't support headers)
    session: Session = Depends(deps.get_session)
):
    """
    Stream Server-Sent Events for real-time game updates.

    Requires authentication. Clients should connect with:
    EventSource('/games/{game_id}/events?token=<session_token>')

    Event types:
    - connected: Initial connection confirmation
    - heartbeat: Keep-alive ping every 30s
    - player_joined: New player joined the lobby
    - player_ready: Player ready status changed
    - game_started: Game transitioned from lobby to in_progress
    - turn_played: Turn was executed
    - purchase_decision: Property purchase modal should appear
    - auction_started: Auction initiated
    - auction_bid: Bid placed in auction
    - auction_resolved: Auction completed
    - game_state_changed: Generic refresh trigger
    """
    # Manually verify session token (EventSource doesn't support custom headers)
    game_session = session.query(models.GameSession).filter_by(
        session_token=token
    ).first()

    if not game_session:
        raise HTTPException(status_code=401, detail="Invalid session token")

    # Check expiration
    if game_session.expires_at < utc_now():
        raise HTTPException(status_code=401, detail="Session token has expired")

    user_id = game_session.user_id
    token_game_id = game_session.game_id

    # Verify the token's game_id matches the requested game_id
    if token_game_id != game_id:
        raise HTTPException(
            status_code=403,
            detail="Session token is for a different game"
        )

    # Verify game exists
    game = deps.get_game_or_404(game_id, session)

    # Verify user is a player in this game
    player = session.query(models.GamePlayer).filter_by(
        game_id=game_id,
        user_id=user_id
    ).first()

    if not player:
        raise HTTPException(
            status_code=403,
            detail="You are not a player in this game"
        )

    # Return SSE stream
    return EventSourceResponse(event_generator(game_id, user_id))
