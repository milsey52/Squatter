# app/api/routes/trades.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, List
import json
import asyncio
from datetime import datetime

from app.api import deps, auth
from app.api.routes.events import broadcast_game_event
from app import models

router = APIRouter()


class InitiateTradeRequest(BaseModel):
    counterparty_player_id: Optional[int] = None  # None means Bank


class UpdateOfferRequest(BaseModel):
    cash: int = 0
    property_ids: List[int] = []
    card_ids: List[int] = []


@router.post("/initiate")
async def initiate_trade(
    game_id: int,
    request: InitiateTradeRequest,
    background_tasks: BackgroundTasks,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """
    Initiate a trade session. Only one active trade allowed per game.
    """
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    game = deps.get_game_or_404(game_id, session)

    # Find initiator's game_player
    initiator = session.query(models.GamePlayer).filter_by(
        game_id=game_id,
        user_id=user_id
    ).first()

    if not initiator:
        raise HTTPException(status_code=403, detail="You are not a player in this game")

    # Check if there's already an active or pending trade
    existing_trade = session.query(models.TradeSession).filter(
        models.TradeSession.game_id == game_id,
        models.TradeSession.status.in_(["pending_invite", "active"])
    ).first()

    if existing_trade:
        raise HTTPException(status_code=400, detail="Another trade is already in progress")

    # Create new trade session
    trade = models.TradeSession(
        game_id=game_id,
        initiator_player_id=initiator.game_player_id,
        counterparty_player_id=request.counterparty_player_id,
        status="pending_invite" if request.counterparty_player_id else "active",  # Bank trades are immediately active
        initiator_offer=json.dumps({"cash": 0, "properties": [], "cards": []}),
        counterparty_offer=json.dumps({"cash": 0, "properties": [], "cards": []})
    )
    session.add(trade)
    session.commit()

    # Broadcast trade initiated event
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
        "initiator_player_id": trade.initiator_player_id,
        "counterparty_player_id": trade.counterparty_player_id
    }


@router.get("/active")
def get_active_trade(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """
    Get the currently active trade session for this game.
    """
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
            "game_id": trade.game_id,
            "initiator_player_id": trade.initiator_player_id,
            "counterparty_player_id": trade.counterparty_player_id,
            "status": trade.status,
            "initiator_offer": json.loads(trade.initiator_offer) if trade.initiator_offer else {},
            "counterparty_offer": json.loads(trade.counterparty_offer) if trade.counterparty_offer else {},
            "initiator_accepted": trade.initiator_accepted,
            "counterparty_accepted": trade.counterparty_accepted,
            "created_at": trade.created_at.isoformat() if trade.created_at else None
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
    """
    Accept or reject a trade invitation.
    """
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    trade = session.query(models.TradeSession).filter_by(
        trade_session_id=trade_id,
        game_id=game_id
    ).first()

    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    # Verify user is the counterparty
    counterparty = session.query(models.GamePlayer).filter_by(
        game_player_id=trade.counterparty_player_id
    ).first()

    if not counterparty or counterparty.user_id != user_id:
        raise HTTPException(status_code=403, detail="You are not invited to this trade")

    if accept:
        trade.status = "active"
    else:
        trade.status = "cancelled"
        trade.completed_at = datetime.now()

    session.commit()

    # Broadcast trade status change
    background_tasks.add_task(
        broadcast_game_event, game_id, "trade_status_changed", {
            "trade_session_id": trade.trade_session_id,
            "status": trade.status,
            "accepted": accept
        }
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
    """
    Cancel the trade. Can be done by either party.
    """
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    trade = session.query(models.TradeSession).filter_by(
        trade_session_id=trade_id,
        game_id=game_id
    ).first()

    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    # Verify user is part of the trade
    user_player = session.query(models.GamePlayer).filter_by(
        game_id=game_id,
        user_id=user_id
    ).first()

    if not user_player or (user_player.game_player_id != trade.initiator_player_id and
                          user_player.game_player_id != trade.counterparty_player_id):
        raise HTTPException(status_code=403, detail="You are not part of this trade")

    trade.status = "cancelled"
    trade.completed_at = datetime.now()
    session.commit()

    # Broadcast trade cancelled event
    background_tasks.add_task(
        broadcast_game_event, game_id, "trade_cancelled", {
            "trade_session_id": trade.trade_session_id
        }
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
    """
    Update your offer in the trade.
    """
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    trade = session.query(models.TradeSession).filter_by(
        trade_session_id=trade_id,
        game_id=game_id,
        status="active"
    ).first()

    if not trade:
        raise HTTPException(status_code=404, detail="No active trade found")

    # Determine if user is initiator or counterparty
    user_player = session.query(models.GamePlayer).filter_by(
        game_id=game_id,
        user_id=user_id
    ).first()

    offer_data = {
        "cash": offer.cash,
        "properties": offer.property_ids,
        "cards": offer.card_ids
    }

    if user_player.game_player_id == trade.initiator_player_id:
        trade.initiator_offer = json.dumps(offer_data)
        # Reset acceptance flags when offer changes
        trade.initiator_accepted = False
        trade.counterparty_accepted = False
    elif user_player.game_player_id == trade.counterparty_player_id:
        trade.counterparty_offer = json.dumps(offer_data)
        # Reset acceptance flags when offer changes
        trade.initiator_accepted = False
        trade.counterparty_accepted = False
    else:
        raise HTTPException(status_code=403, detail="You are not part of this trade")

    trade.updated_at = datetime.now()
    session.commit()

    # Broadcast offer updated event with full trade details
    background_tasks.add_task(
        broadcast_game_event, game_id, "trade_offer_updated", {
            "trade_session_id": trade.trade_session_id,
            "updated_by": user_player.game_player_id,
            "initiator_offer": json.loads(trade.initiator_offer) if trade.initiator_offer else {},
            "counterparty_offer": json.loads(trade.counterparty_offer) if trade.counterparty_offer else {},
            "initiator_accepted": trade.initiator_accepted,
            "counterparty_accepted": trade.counterparty_accepted
        }
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
    """
    Accept/confirm the trade. Both parties must accept before trade can be executed.
    """
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    trade = session.query(models.TradeSession).filter_by(
        trade_session_id=trade_id,
        game_id=game_id,
        status="active"
    ).first()

    if not trade:
        raise HTTPException(status_code=404, detail="No active trade found")

    # Determine if user is initiator or counterparty
    user_player = session.query(models.GamePlayer).filter_by(
        game_id=game_id,
        user_id=user_id
    ).first()

    if user_player.game_player_id == trade.initiator_player_id:
        trade.initiator_accepted = True
    elif user_player.game_player_id == trade.counterparty_player_id:
        trade.counterparty_accepted = True
    else:
        raise HTTPException(status_code=403, detail="You are not part of this trade")

    trade.updated_at = datetime.now()
    session.commit()

    # Broadcast acceptance event
    background_tasks.add_task(
        broadcast_game_event, game_id, "trade_accepted", {
            "trade_session_id": trade.trade_session_id,
            "accepted_by": user_player.game_player_id,
            "initiator_accepted": trade.initiator_accepted,
            "counterparty_accepted": trade.counterparty_accepted,
            "both_accepted": trade.initiator_accepted and trade.counterparty_accepted
        }
    )

    return {
        "status": "accepted",
        "initiator_accepted": trade.initiator_accepted,
        "counterparty_accepted": trade.counterparty_accepted,
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
    """
    Execute the trade (both parties agree).
    For now, this is a placeholder - actual asset transfer logic will be added.
    """
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    trade = session.query(models.TradeSession).filter_by(
        trade_session_id=trade_id,
        game_id=game_id,
        status="active"
    ).first()

    if not trade:
        raise HTTPException(status_code=404, detail="No active trade found")

    # Check if this is a Bank trade (mortgage)
    is_bank_trade = trade.counterparty_player_id is None

    # For player-to-player trades, require both parties to have accepted
    if not is_bank_trade:
        if not trade.initiator_accepted or not trade.counterparty_accepted:
            raise HTTPException(
                status_code=400,
                detail="Both parties must accept the trade before it can be executed"
            )

    if is_bank_trade:
        # Handle Bank mortgage trade
        from app.services.ledger_service import LedgerService

        # Parse initiator's offer
        initiator_offer = json.loads(trade.initiator_offer) if isinstance(trade.initiator_offer, str) else trade.initiator_offer
        property_ids = initiator_offer.get("properties", [])

        if not property_ids:
            raise HTTPException(status_code=400, detail="No properties selected for mortgage")

        # Get initiator player
        initiator = session.query(models.GamePlayer).filter_by(
            game_player_id=trade.initiator_player_id
        ).first()

        if not initiator:
            raise HTTPException(status_code=404, detail="Initiator player not found")

        # Validate and mortgage each property
        total_mortgage_value = 0

        # Get current turn_id (if any)
        current_turn = session.query(models.Turn).filter_by(
            game_id=game_id
        ).order_by(models.Turn.turn_id.desc()).first()
        turn_id = current_turn.turn_id if current_turn else None

        # Transfer mortgage payment from Bank to player
        ledger = LedgerService(session, game_id)

        for asset_id in property_ids:
            # Get asset and its state
            asset = session.query(models.Asset).filter_by(asset_id=asset_id).first()
            asset_state = session.query(models.AssetState).filter_by(
                game_id=game_id,
                asset_id=asset_id
            ).first()

            if not asset or not asset_state:
                raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")

            # Validate ownership
            if asset_state.owner_game_player_id != trade.initiator_player_id:
                raise HTTPException(status_code=403, detail=f"Player does not own asset {asset_id}")

            # NEW RULE: Check if ANY property in the same group has improvements
            # Find all properties in the same group (same purchase price and rent structure)
            group_assets = (
                session.query(models.Asset, models.AssetState, models.Space.name)
                .join(models.AssetState, models.Asset.asset_id == models.AssetState.asset_id)
                .join(models.Space, models.Asset.space_id == models.Space.space_id)
                .filter(
                    models.AssetState.game_id == game_id,
                    models.Asset.asset_type == 'property',
                    models.Asset.purchase_price == asset.purchase_price,
                    models.Asset.rent_house_1 == asset.rent_house_1,
                    models.Asset.rent_hotel == asset.rent_hotel
                )
                .all()
            )

            # Check if any property in the group has improvements
            for group_asset, group_state, group_name in group_assets:
                if group_state.improvement_level > 0 or group_state.has_hotel:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Cannot mortgage - property '{group_name}' in this group has improvements. Sell all houses/hotels in the group first."
                    )

            # Validate not already mortgaged
            if asset_state.is_mortgaged:
                raise HTTPException(status_code=400, detail=f"Property {asset_id} is already mortgaged")

            # Mark as mortgaged
            asset_state.is_mortgaged = True
            total_mortgage_value += asset.mortgage_value

            # Create a separate transaction for each mortgaged property
            ledger.receive_from_bank(
                player=initiator,
                amount=asset.mortgage_value,
                txn_type="mortgage",
                turn_id=turn_id,
                asset_id=asset_id,
                notes=f"Mortgaged property"
            )
    else:
        # Implement player-to-player trade logic
        from app.services.ledger_service import LedgerService

        # Parse offers
        initiator_offer = json.loads(trade.initiator_offer) if isinstance(trade.initiator_offer, str) else trade.initiator_offer
        counterparty_offer = json.loads(trade.counterparty_offer) if isinstance(trade.counterparty_offer, str) else trade.counterparty_offer

        initiator_cash = initiator_offer.get("cash", 0)
        initiator_properties = initiator_offer.get("properties", [])
        initiator_cards = initiator_offer.get("cards", [])

        counterparty_cash = counterparty_offer.get("cash", 0)
        counterparty_properties = counterparty_offer.get("properties", [])
        counterparty_cards = counterparty_offer.get("cards", [])

        # Get players
        initiator = session.query(models.GamePlayer).filter_by(
            game_player_id=trade.initiator_player_id
        ).first()
        counterparty = session.query(models.GamePlayer).filter_by(
            game_player_id=trade.counterparty_player_id
        ).first()

        if not initiator or not counterparty:
            raise HTTPException(status_code=404, detail="Player not found")

        # Get current turn
        current_turn = session.query(models.Turn).filter_by(
            game_id=game_id
        ).order_by(models.Turn.turn_id.desc()).first()
        turn_id = current_turn.turn_id if current_turn else None

        ledger = LedgerService(session, game_id)

        # Validate initiator has what they're offering
        if initiator_cash > 0:
            initiator_balance = ledger.get_balance(initiator.game_player_id)
            if initiator_balance < initiator_cash:
                raise HTTPException(status_code=400, detail=f"{initiator.player_name} doesn't have ${initiator_cash}")

        for asset_id in initiator_properties:
            asset_state = session.query(models.AssetState).filter_by(
                game_id=game_id,
                asset_id=asset_id
            ).first()
            if not asset_state or asset_state.owner_game_player_id != initiator.game_player_id:
                raise HTTPException(status_code=400, detail=f"{initiator.player_name} doesn't own property {asset_id}")
            if asset_state.is_mortgaged:
                raise HTTPException(status_code=400, detail=f"Property {asset_id} is mortgaged and cannot be traded")

        # Validate counterparty has what they're offering
        if counterparty_cash > 0:
            counterparty_balance = ledger.get_balance(counterparty.game_player_id)
            if counterparty_balance < counterparty_cash:
                raise HTTPException(status_code=400, detail=f"{counterparty.player_name} doesn't have ${counterparty_cash}")

        for asset_id in counterparty_properties:
            asset_state = session.query(models.AssetState).filter_by(
                game_id=game_id,
                asset_id=asset_id
            ).first()
            if not asset_state or asset_state.owner_game_player_id != counterparty.game_player_id:
                raise HTTPException(status_code=400, detail=f"{counterparty.player_name} doesn't own property {asset_id}")
            if asset_state.is_mortgaged:
                raise HTTPException(status_code=400, detail=f"Property {asset_id} is mortgaged and cannot be traded")

        # Execute the trade
        # 1. Transfer cash from initiator to counterparty
        if initiator_cash > 0:
            ledger.pay_player(
                from_player=initiator,
                to_player=counterparty,
                amount=initiator_cash,
                txn_type="trade",
                turn_id=turn_id,
                notes=f"Trade payment from {initiator.player_name} to {counterparty.player_name}"
            )

        # 2. Transfer cash from counterparty to initiator
        if counterparty_cash > 0:
            ledger.pay_player(
                from_player=counterparty,
                to_player=initiator,
                amount=counterparty_cash,
                txn_type="trade",
                turn_id=turn_id,
                notes=f"Trade payment from {counterparty.player_name} to {initiator.player_name}"
            )

        # 3. Transfer properties from initiator to counterparty
        for asset_id in initiator_properties:
            asset_state = session.query(models.AssetState).filter_by(
                game_id=game_id,
                asset_id=asset_id
            ).first()
            asset_state.owner_game_player_id = counterparty.game_player_id

        # 4. Transfer properties from counterparty to initiator
        for asset_id in counterparty_properties:
            asset_state = session.query(models.AssetState).filter_by(
                game_id=game_id,
                asset_id=asset_id
            ).first()
            asset_state.owner_game_player_id = initiator.game_player_id

        # 5. Transfer cards from initiator to counterparty
        for card_id in initiator_cards:
            card_draw = session.query(models.CardDraw).filter_by(
                card_draw_id=card_id,
                kept_by_player_id=initiator.game_player_id
            ).first()
            if card_draw:
                card_draw.kept_by_player_id = counterparty.game_player_id

        # 6. Transfer cards from counterparty to initiator
        for card_id in counterparty_cards:
            card_draw = session.query(models.CardDraw).filter_by(
                card_draw_id=card_id,
                kept_by_player_id=counterparty.game_player_id
            ).first()
            if card_draw:
                card_draw.kept_by_player_id = initiator.game_player_id

    trade.status = "completed"
    trade.completed_at = datetime.now()
    session.commit()

    # Broadcast trade executed event
    background_tasks.add_task(
        broadcast_game_event, game_id, "trade_executed", {
            "trade_session_id": trade.trade_session_id
        }
    )

    return {"status": "completed"}
