# app/api/routes/decisions.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.api import deps, auth
from app import models
from app.services.decision_service import DecisionService
from app.api.routes import events
import asyncio

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
async def buy_property(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Buy the property (for current pending purchase decision)."""
    user_id, token_game_id = auth_data

    # Verify the token's game_id matches the requested game_id
    if token_game_id != game_id:
        raise HTTPException(
            status_code=403,
            detail="Session token is for a different game"
        )

    deps.get_game_or_404(game_id, session)
    service = DecisionService(session, game_id)

    pending = service.get_pending_action()
    if not pending:
        raise HTTPException(status_code=400, detail="No pending action")

    # Verify the user owns the active player
    active_player = session.query(models.GamePlayer).filter_by(
        game_player_id=pending.active_player_id
    ).first()

    if not active_player or active_player.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="This decision belongs to another player"
        )

    try:
        result = service.buy_property(pending.active_player_id)
        session.commit()

        # Broadcast purchase decision resolved
        await events.broadcast_game_event(
            game_id,
            "game_state_changed",
            {"reason": "property_purchased", "asset_id": pending.asset_id}
        )

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/decisions/pass")
async def pass_property(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Pass on property, potentially starting auction."""
    user_id, token_game_id = auth_data

    # Verify the token's game_id matches the requested game_id
    if token_game_id != game_id:
        raise HTTPException(
            status_code=403,
            detail="Session token is for a different game"
        )

    deps.get_game_or_404(game_id, session)
    service = DecisionService(session, game_id)

    pending = service.get_pending_action()
    if not pending:
        raise HTTPException(status_code=400, detail="No pending action")

    # Verify the user owns the active player
    active_player = session.query(models.GamePlayer).filter_by(
        game_player_id=pending.active_player_id
    ).first()

    if not active_player or active_player.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="This decision belongs to another player"
        )

    try:
        result = service.pass_property(pending.active_player_id)
        session.commit()

        # Broadcast auction started if applicable
        if result.get("status") == "auction_started":
            await events.broadcast_game_event(
                game_id,
                "auction_started",
                {"asset_id": pending.asset_id}
            )

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/auctions/bid")
async def place_bid(
    game_id: int,
    body: BidRequest,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Place bid in auction."""
    user_id, token_game_id = auth_data

    # Verify the token's game_id matches the requested game_id
    if token_game_id != game_id:
        raise HTTPException(
            status_code=403,
            detail="Session token is for a different game"
        )

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
    current_bidder_id = active_bidders[current_idx % len(active_bidders)]

    # Verify the user owns the current bidder
    current_bidder = session.query(models.GamePlayer).filter_by(
        game_player_id=current_bidder_id
    ).first()

    if not current_bidder or current_bidder.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="It is not your turn to bid"
        )

    try:
        result = service.place_bid(current_bidder_id, body.amount)
        session.commit()

        # Broadcast auction bid or auction resolved
        if result.get("status") == "auction_resolved":
            await events.broadcast_game_event(
                game_id,
                "auction_resolved",
                {"winner_id": result.get("winner_id"), "winning_bid": result.get("winning_bid")}
            )
        else:
            await events.broadcast_game_event(
                game_id,
                "auction_bid",
                {
                    "bidder_id": current_bidder_id,
                    "amount": body.amount,
                    "next_bidder_id": result.get("next_bidder_id"),
                    "current_bid": result.get("current_bid")
                }
            )

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/auctions/pass")
async def pass_auction(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Pass on bidding."""
    user_id, token_game_id = auth_data

    # Verify the token's game_id matches the requested game_id
    if token_game_id != game_id:
        raise HTTPException(
            status_code=403,
            detail="Session token is for a different game"
        )

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
    current_bidder_id = active_bidders[current_idx % len(active_bidders)]

    # Verify the user owns the current bidder
    current_bidder = session.query(models.GamePlayer).filter_by(
        game_player_id=current_bidder_id
    ).first()

    if not current_bidder or current_bidder.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="It is not your turn to bid"
        )

    try:
        result = service.pass_auction(current_bidder_id)
        session.commit()

        # Broadcast auction pass or auction resolved
        if result.get("status") == "auction_resolved":
            await events.broadcast_game_event(
                game_id,
                "auction_resolved",
                {"winner_id": result.get("winner_id"), "winning_bid": result.get("winning_bid")}
            )
        else:
            await events.broadcast_game_event(
                game_id,
                "auction_pass",
                {
                    "player_id": current_bidder_id,
                    "next_bidder_id": result.get("next_bidder_id"),
                    "remaining_bidders": result.get("remaining_bidders")
                }
            )

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/decisions/acknowledge-card")
async def acknowledge_card(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Acknowledge a drawn card and apply its effect."""
    import json
    from app.services.card_service import CardService
    from app.services.space_resolver import SpaceResolver
    from datetime import datetime

    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    deps.get_game_or_404(game_id, session)

    pending = session.query(models.PendingAction).filter_by(
        game_id=game_id,
        action_type="card_drawn"
    ).filter(models.PendingAction.resolved_at.is_(None)).first()

    if not pending:
        raise HTTPException(status_code=400, detail="No card drawn action found")

    # Verify the user owns the active player
    active_player = session.query(models.GamePlayer).filter_by(
        game_player_id=pending.active_player_id
    ).first()

    if not active_player or active_player.user_id != user_id:
        raise HTTPException(status_code=403, detail="This card belongs to another player")

    # Parse card data
    card_data = json.loads(pending.action_data)
    card_id = card_data["card_id"]
    card_draw_id = card_data["card_draw_id"]
    is_retainable = card_data["is_retainable"]

    # Get card and apply effect
    card = session.query(models.Card).get(card_id)
    card_draw = session.query(models.CardDraw).get(card_draw_id)

    if is_retainable:
        # Keep the card
        card_draw.kept_by_player_id = active_player.game_player_id
    else:
        # Apply effect and discard
        space_resolver = SpaceResolver(session, game_id)
        card_service = CardService(session, game_id, space_resolver=space_resolver)
        space_resolver.card_service = card_service

        turn = session.query(models.Turn).get(pending.turn_id)
        card_service._apply_effect(card, active_player, turn)

        card_draw.discarded_at = datetime.now()

    # Mark pending action as resolved
    pending.resolved_at = datetime.now()
    session.commit()

    # Broadcast card acknowledged (await to ensure it completes before response)
    await events.broadcast_game_event(
        game_id,
        "game_state_changed",
        {"reason": "card_acknowledged", "card_id": card_id}
    )

    return {"status": "acknowledged", "card_name": card_data["card_name"]}


@router.post("/decisions/pay-rent")
async def pay_rent(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Confirm rent payment."""
    import json
    from app.services.ledger_service import LedgerService
    from datetime import datetime

    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    deps.get_game_or_404(game_id, session)

    pending = session.query(models.PendingAction).filter_by(
        game_id=game_id,
        action_type="rent_payment"
    ).filter(models.PendingAction.resolved_at.is_(None)).first()

    if not pending:
        raise HTTPException(status_code=400, detail="No rent payment action found")

    # Verify the user owns the active player
    active_player = session.query(models.GamePlayer).filter_by(
        game_player_id=pending.active_player_id
    ).first()

    if not active_player or active_player.user_id != user_id:
        raise HTTPException(status_code=403, detail="This rent payment belongs to another player")

    # Parse rent data
    rent_data = json.loads(pending.action_data)
    rent_amount = rent_data["rent_amount"]
    landlord_id = rent_data["landlord_id"]
    txn_type = rent_data.get("txn_type", "rent")

    # Process rent payment
    ledger = LedgerService(session, game_id)
    ledger.transfer(
        payer=active_player,
        payee_id=landlord_id,
        amount=rent_amount,
        txn_type=txn_type,
        turn_id=pending.turn_id,
        asset_id=pending.asset_id,
    )

    # Mark pending action as resolved
    pending.resolved_at = datetime.now()
    session.commit()

    # Broadcast rent paid
    await events.broadcast_game_event(
        game_id,
        "game_state_changed",
        {"reason": "rent_paid", "amount": rent_amount, "landlord_id": landlord_id}
    )

    return {"status": "paid", "amount": rent_amount}


@router.post("/decisions/acknowledge-jail")
async def acknowledge_jail(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Player acknowledges going to jail and is moved to jail space."""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    deps.get_game_or_404(game_id, session)

    # Find the current user's player
    user_player = session.query(models.GamePlayer).filter_by(
        game_id=game_id,
        user_id=user_id
    ).first()

    if not user_player:
        raise HTTPException(status_code=403, detail="You are not a player in this game")

    # Acknowledge jail via DecisionService
    decision_service = DecisionService(session, game_id)

    try:
        result = decision_service.acknowledge_jail(user_player.game_player_id)
        session.commit()

        # Broadcast jail event and game state change (await to ensure they complete before response)
        await events.broadcast_game_event(
            game_id,
            "player_jailed",
            {
                "player_id": user_player.game_player_id,
                "player_name": user_player.player_name,
                "has_get_out_card": result["has_get_out_card"]
            }
        )

        await events.broadcast_game_event(
            game_id,
            "game_state_changed",
            {"reason": "jail_acknowledged", "player_id": user_player.game_player_id}
        )

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
