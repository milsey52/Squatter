# app/api/routes/decisions.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.api import deps
from app.services.decision_service import DecisionService

router = APIRouter()


class BidRequest(BaseModel):
    amount: int


@router.get("/pending-action")
def get_pending_action(game_id: int, session: Session = Depends(deps.get_session)):
    """Get current pending action (if any)."""
    deps.get_game_or_404(game_id, session)
    service = DecisionService(session, game_id)
    action = service.get_auction_state()
    if not action:
        return {"pending_action": None}
    return {"pending_action": action}


@router.post("/decisions/buy")
def buy_property(game_id: int, session: Session = Depends(deps.get_session)):
    """Buy the property (for current pending purchase decision)."""
    deps.get_game_or_404(game_id, session)
    service = DecisionService(session, game_id)

    pending = service.get_pending_action()
    if not pending:
        raise HTTPException(status_code=400, detail="No pending action")

    try:
        result = service.buy_property(pending.active_player_id)
        session.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/decisions/pass")
def pass_property(game_id: int, session: Session = Depends(deps.get_session)):
    """Pass on property, potentially starting auction."""
    deps.get_game_or_404(game_id, session)
    service = DecisionService(session, game_id)

    pending = service.get_pending_action()
    if not pending:
        raise HTTPException(status_code=400, detail="No pending action")

    try:
        result = service.pass_property(pending.active_player_id)
        session.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/auctions/bid")
def place_bid(game_id: int, body: BidRequest, session: Session = Depends(deps.get_session)):
    """Place bid in auction."""
    deps.get_game_or_404(game_id, session)
    service = DecisionService(session, game_id)

    pending = service.get_pending_action()
    if not pending:
        raise HTTPException(status_code=400, detail="No active auction")
    if pending.action_type != "auction":
        raise HTTPException(status_code=400, detail="No active auction")

    # Get current bidder from auction state
    import json
    auction = json.loads(pending.action_data) if pending.action_data else {}
    active_bidders = auction.get("active_bidders", [])
    current_idx = auction.get("current_bidder_index", 0)
    if not active_bidders:
        raise HTTPException(status_code=400, detail="No active bidders")
    current_bidder = active_bidders[current_idx % len(active_bidders)]

    try:
        result = service.place_bid(current_bidder, body.amount)
        session.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/auctions/pass")
def pass_auction(game_id: int, session: Session = Depends(deps.get_session)):
    """Pass on bidding."""
    deps.get_game_or_404(game_id, session)
    service = DecisionService(session, game_id)

    pending = service.get_pending_action()
    if not pending:
        raise HTTPException(status_code=400, detail="No active auction")
    if pending.action_type != "auction":
        raise HTTPException(status_code=400, detail="No active auction")

    # Get current bidder from auction state
    import json
    auction = json.loads(pending.action_data) if pending.action_data else {}
    active_bidders = auction.get("active_bidders", [])
    current_idx = auction.get("current_bidder_index", 0)
    if not active_bidders:
        raise HTTPException(status_code=400, detail="No active bidders")
    current_bidder = active_bidders[current_idx % len(active_bidders)]

    try:
        result = service.pass_auction(current_bidder)
        session.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
