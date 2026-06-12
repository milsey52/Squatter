# app/api/routes/trades.py
"""Trades in Squatter: players can trade cash and stud rams."""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, List
import json
from app.utils.time import utc_now

from app.api import deps, auth
from app.api.routes.events import broadcast_game_event
from app import models

router = APIRouter()


class InitiateTradeRequest(BaseModel):
    counterparty_player_id: int


class UpdateOfferRequest(BaseModel):
    cash: int = 0
    stud_ram_space_ids: List[int] = []


@router.post("/initiate")
async def initiate_trade(
    game_id: int,
    request: InitiateTradeRequest,
    background_tasks: BackgroundTasks,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Initiate a trade session."""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    deps.get_game_or_404(game_id, session)

    initiator = session.query(models.GamePlayer).filter_by(
        game_id=game_id, user_id=user_id
    ).first()

    if not initiator:
        raise HTTPException(status_code=403, detail="You are not a player in this game")

    # Check if there's already an active trade
    existing_trade = session.query(models.TradeSession).filter(
        models.TradeSession.game_id == game_id,
        models.TradeSession.status.in_(["pending_invite", "active"])
    ).first()

    if existing_trade:
        raise HTTPException(status_code=400, detail="Another trade is already in progress")

    trade = models.TradeSession(
        game_id=game_id,
        initiator_player_id=initiator.game_player_id,
        counterparty_player_id=request.counterparty_player_id,
        status="pending_invite",
        initiator_offer=json.dumps({"cash": 0, "stud_ram_space_ids": []}),
        counterparty_offer=json.dumps({"cash": 0, "stud_ram_space_ids": []})
    )
    session.add(trade)
    session.commit()

    background_tasks.add_task(
        broadcast_game_event, game_id, "trade_initiated", {
            "trade_session_id": trade.trade_session_id,
            "status": trade.status,
            "initiator_player_id": trade.initiator_player_id,
            "counterparty_player_id": trade.counterparty_player_id
        }
    )

    return {
        "trade_session_id": trade.trade_session_id,
        "status": trade.status,
    }


@router.get("/active")
def get_active_trade(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Get the currently active trade session."""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    trade = session.query(models.TradeSession).filter(
        models.TradeSession.game_id == game_id,
        models.TradeSession.status.in_(["pending_invite", "active"])
    ).first()

    if not trade:
        return {"trade": None}

    return {
        "trade": {
            "trade_session_id": trade.trade_session_id,
            "initiator_player_id": trade.initiator_player_id,
            "counterparty_player_id": trade.counterparty_player_id,
            "status": trade.status,
            "initiator_offer": json.loads(trade.initiator_offer) if trade.initiator_offer else {},
            "counterparty_offer": json.loads(trade.counterparty_offer) if trade.counterparty_offer else {},
            "initiator_accepted": trade.initiator_accepted,
            "counterparty_accepted": trade.counterparty_accepted,
        }
    }


@router.post("/{trade_id}/accept-invite")
async def accept_trade_invite(
    game_id: int,
    trade_id: int,
    accept: bool,
    background_tasks: BackgroundTasks,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Accept or reject a trade invitation."""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    trade = session.query(models.TradeSession).filter_by(
        trade_session_id=trade_id, game_id=game_id
    ).first()

    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    counterparty = session.query(models.GamePlayer).filter_by(
        game_player_id=trade.counterparty_player_id
    ).first()

    if not counterparty or counterparty.user_id != user_id:
        raise HTTPException(status_code=403, detail="You are not invited to this trade")

    if accept:
        trade.status = "active"
    else:
        trade.status = "cancelled"
        trade.completed_at = utc_now()

    session.commit()

    background_tasks.add_task(
        broadcast_game_event, game_id, "trade_status_changed",
        {"trade_session_id": trade.trade_session_id, "status": trade.status}
    )

    return {"status": trade.status}


@router.post("/{trade_id}/cancel")
async def cancel_trade(
    game_id: int,
    trade_id: int,
    background_tasks: BackgroundTasks,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Cancel the trade."""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    trade = session.query(models.TradeSession).filter_by(
        trade_session_id=trade_id, game_id=game_id
    ).first()

    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    user_player = session.query(models.GamePlayer).filter_by(
        game_id=game_id, user_id=user_id
    ).first()

    if not user_player or (user_player.game_player_id != trade.initiator_player_id and
                          user_player.game_player_id != trade.counterparty_player_id):
        raise HTTPException(status_code=403, detail="You are not part of this trade")

    trade.status = "cancelled"
    trade.completed_at = utc_now()
    session.commit()

    background_tasks.add_task(
        broadcast_game_event, game_id, "trade_cancelled",
        {"trade_session_id": trade.trade_session_id}
    )

    return {"status": "cancelled"}


@router.post("/{trade_id}/update-offer")
async def update_offer(
    game_id: int,
    trade_id: int,
    offer: UpdateOfferRequest,
    background_tasks: BackgroundTasks,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Update your offer in the trade."""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    trade = session.query(models.TradeSession).filter_by(
        trade_session_id=trade_id, game_id=game_id, status="active"
    ).first()

    if not trade:
        raise HTTPException(status_code=404, detail="No active trade found")

    user_player = session.query(models.GamePlayer).filter_by(
        game_id=game_id, user_id=user_id
    ).first()

    offer_data = json.dumps({
        "cash": offer.cash,
        "stud_ram_space_ids": offer.stud_ram_space_ids
    })

    if user_player.game_player_id == trade.initiator_player_id:
        trade.initiator_offer = offer_data
        trade.initiator_accepted = False
        trade.counterparty_accepted = False
    elif user_player.game_player_id == trade.counterparty_player_id:
        trade.counterparty_offer = offer_data
        trade.initiator_accepted = False
        trade.counterparty_accepted = False
    else:
        raise HTTPException(status_code=403, detail="You are not part of this trade")

    trade.updated_at = utc_now()
    session.commit()

    background_tasks.add_task(
        broadcast_game_event, game_id, "trade_offer_updated",
        {"trade_session_id": trade.trade_session_id, "updated_by": user_player.game_player_id}
    )

    return {"status": "offer_updated"}


@router.post("/{trade_id}/accept")
async def accept_trade(
    game_id: int,
    trade_id: int,
    background_tasks: BackgroundTasks,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Accept the trade. Both parties must accept."""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    trade = session.query(models.TradeSession).filter_by(
        trade_session_id=trade_id, game_id=game_id, status="active"
    ).first()

    if not trade:
        raise HTTPException(status_code=404, detail="No active trade found")

    user_player = session.query(models.GamePlayer).filter_by(
        game_id=game_id, user_id=user_id
    ).first()

    if user_player.game_player_id == trade.initiator_player_id:
        trade.initiator_accepted = True
    elif user_player.game_player_id == trade.counterparty_player_id:
        trade.counterparty_accepted = True
    else:
        raise HTTPException(status_code=403, detail="You are not part of this trade")

    trade.updated_at = utc_now()
    session.commit()

    background_tasks.add_task(
        broadcast_game_event, game_id, "trade_accepted",
        {
            "trade_session_id": trade.trade_session_id,
            "both_accepted": trade.initiator_accepted and trade.counterparty_accepted
        }
    )

    return {
        "status": "accepted",
        "both_accepted": trade.initiator_accepted and trade.counterparty_accepted
    }


@router.post("/{trade_id}/execute")
async def execute_trade(
    game_id: int,
    trade_id: int,
    background_tasks: BackgroundTasks,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Execute the trade after both parties accept."""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    trade = session.query(models.TradeSession).filter_by(
        trade_session_id=trade_id, game_id=game_id, status="active"
    ).first()

    if not trade:
        raise HTTPException(status_code=404, detail="No active trade found")

    if not trade.initiator_accepted or not trade.counterparty_accepted:
        raise HTTPException(status_code=400, detail="Both parties must accept before executing")

    # Parse offers
    initiator_offer = json.loads(trade.initiator_offer)
    counterparty_offer = json.loads(trade.counterparty_offer)

    initiator = session.query(models.GamePlayer).filter_by(
        game_player_id=trade.initiator_player_id
    ).first()
    counterparty = session.query(models.GamePlayer).filter_by(
        game_player_id=trade.counterparty_player_id
    ).first()

    if not initiator or not counterparty:
        raise HTTPException(status_code=404, detail="Player not found")

    from app.services.ledger_service import LedgerService
    ledger = LedgerService(session, game_id)

    turn = session.query(models.Turn).filter_by(
        game_id=game_id
    ).order_by(models.Turn.turn_id.desc()).first()
    turn_id = turn.turn_id if turn else None

    # Transfer cash
    initiator_cash = initiator_offer.get("cash", 0)
    counterparty_cash = counterparty_offer.get("cash", 0)

    if initiator_cash > 0:
        balance = ledger.get_balance(initiator.game_player_id)
        if balance < initiator_cash:
            raise HTTPException(status_code=400, detail=f"{initiator.player_name} doesn't have ${initiator_cash}")
        ledger.pay_player(initiator, counterparty, initiator_cash, "trade", turn_id,
                         notes="Trade payment")

    if counterparty_cash > 0:
        balance = ledger.get_balance(counterparty.game_player_id)
        if balance < counterparty_cash:
            raise HTTPException(status_code=400, detail=f"{counterparty.player_name} doesn't have ${counterparty_cash}")
        ledger.pay_player(counterparty, initiator, counterparty_cash, "trade", turn_id,
                         notes="Trade payment")

    # Transfer stud rams
    for space_id in initiator_offer.get("stud_ram_space_ids", []):
        ram = session.query(models.StudRamState).filter_by(
            game_id=game_id, space_id=space_id, owner_game_player_id=initiator.game_player_id
        ).first()
        if not ram:
            raise HTTPException(status_code=400, detail=f"{initiator.player_name} doesn't own stud ram at space {space_id}")
        ram.owner_game_player_id = counterparty.game_player_id

    for space_id in counterparty_offer.get("stud_ram_space_ids", []):
        ram = session.query(models.StudRamState).filter_by(
            game_id=game_id, space_id=space_id, owner_game_player_id=counterparty.game_player_id
        ).first()
        if not ram:
            raise HTTPException(status_code=400, detail=f"{counterparty.player_name} doesn't own stud ram at space {space_id}")
        ram.owner_game_player_id = initiator.game_player_id

    trade.status = "completed"
    trade.completed_at = utc_now()

    session.commit()

    background_tasks.add_task(
        broadcast_game_event, game_id, "trade_executed",
        {"trade_session_id": trade.trade_session_id}
    )

    return {"status": "completed"}
