# app/api/routes/decisions.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from app.api import deps, auth
from app import models
from app.services.decision_service import DecisionService
from app.api.routes import events

router = APIRouter()


class StockSaleRequest(BaseModel):
    action: str  # "buy", "sell", "pass"
    pens: Optional[int] = None
    use_high_stock_prices: bool = False
    use_auto_sell_modifier: bool = True  # opt-out of the +20% earned from enhanced expenses


class TuckerBagRequest(BaseModel):
    buy_card: bool = False


@router.get("/pending-action")
def get_pending_action(game_id: int, session: Session = Depends(deps.get_session)):
    """Get current pending action (if any)."""
    deps.get_game_or_404(game_id, session)
    service = DecisionService(session, game_id)
    action = service.get_pending_action_state()
    if not action:
        return {"pending_action": None}
    return {"pending_action": action}


@router.post("/decisions/stock-sale")
async def stock_sale_decision(
    game_id: int,
    body: StockSaleRequest,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Handle stock sale decision: buy, sell, or pass."""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    deps.get_game_or_404(game_id, session)
    service = DecisionService(session, game_id)

    player = _get_active_player(session, service, user_id)

    try:
        if body.action == "buy":
            if not body.pens or body.pens <= 0:
                raise ValueError("Must specify positive number of pens to buy")
            result = service.stock_sale_buy(player.game_player_id, body.pens,
                                            use_high_stock_prices=body.use_high_stock_prices)
        elif body.action == "sell":
            if not body.pens or body.pens <= 0:
                raise ValueError("Must specify positive number of pens to sell")
            result = service.stock_sale_sell(player.game_player_id, body.pens,
                                             use_high_stock_prices=body.use_high_stock_prices,
                                             use_auto_sell_modifier=body.use_auto_sell_modifier)
        elif body.action == "pass":
            result = service.stock_sale_pass(player.game_player_id)
        else:
            raise ValueError(f"Invalid action: {body.action}")

        session.commit()

        await events.broadcast_game_event(
            game_id, "game_state_changed",
            {"reason": "stock_sale_resolved", "result": result}
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/decisions/stud-ram-buy")
async def stud_ram_buy(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Buy the stud ram."""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    deps.get_game_or_404(game_id, session)
    service = DecisionService(session, game_id)
    player = _get_active_player(session, service, user_id)

    try:
        result = service.stud_ram_buy(player.game_player_id)
        session.commit()

        await events.broadcast_game_event(
            game_id, "game_state_changed",
            {"reason": "stud_ram_purchased", "result": result}
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/decisions/stud-ram-pass")
async def stud_ram_pass(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Pass on stud ram purchase."""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    deps.get_game_or_404(game_id, session)
    service = DecisionService(session, game_id)
    player = _get_active_player(session, service, user_id)

    try:
        result = service.stud_ram_pass(player.game_player_id)
        session.commit()

        await events.broadcast_game_event(
            game_id, "game_state_changed",
            {"reason": "stud_ram_passed"}
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/decisions/tucker-bag")
async def tucker_bag_acknowledge(
    game_id: int,
    body: TuckerBagRequest = TuckerBagRequest(),
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Acknowledge a Tucker Bag card (and optionally buy retainable cards)."""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    deps.get_game_or_404(game_id, session)
    service = DecisionService(session, game_id)
    player = _get_active_player(session, service, user_id)

    try:
        result = service.tucker_bag_acknowledge(player.game_player_id, buy_card=body.buy_card)
        session.commit()

        await events.broadcast_game_event(
            game_id, "game_state_changed",
            {"reason": "tucker_bag_acknowledged", "result": result}
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class ExpenseRequest(BaseModel):
    buy_card: bool = False
    option: Optional[str] = None  # 'basic' or 'enhanced' for alternative-payment expenses


class FireFightingOfferRequest(BaseModel):
    accept: bool


class FireFightingAuctionBidRequest(BaseModel):
    bid: int


def _get_my_player(session: Session, game_id: int, user_id: int) -> models.GamePlayer:
    """Return the active GamePlayer for this user in this game, or 403."""
    player = (
        session.query(models.GamePlayer)
        .filter_by(game_id=game_id, user_id=user_id, is_active=True)
        .first()
    )
    if not player:
        raise HTTPException(status_code=403, detail="Not a player in this game")
    return player


@router.post("/decisions/fire-fighting-auction-bid")
async def fire_fighting_auction_bid(
    game_id: int,
    body: FireFightingAuctionBidRequest,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session),
):
    user_id, token_game_id = auth_data
    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")
    deps.get_game_or_404(game_id, session)
    service = DecisionService(session, game_id)
    player = _get_my_player(session, game_id, user_id)
    try:
        result = service.fire_fighting_auction_bid(player.game_player_id, body.bid)
        session.commit()
        await events.broadcast_game_event(
            game_id, "game_state_changed",
            {"reason": "fire_fighting_auction_bid", "result": result},
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/decisions/fire-fighting-auction-decline")
async def fire_fighting_auction_decline(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session),
):
    user_id, token_game_id = auth_data
    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")
    deps.get_game_or_404(game_id, session)
    service = DecisionService(session, game_id)
    player = _get_my_player(session, game_id, user_id)
    try:
        result = service.fire_fighting_auction_decline(player.game_player_id)
        session.commit()
        await events.broadcast_game_event(
            game_id, "game_state_changed",
            {"reason": "fire_fighting_auction_decline", "result": result},
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/decisions/fire-fighting-offer")
async def fire_fighting_offer(
    game_id: int,
    body: FireFightingOfferRequest,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session),
):
    user_id, token_game_id = auth_data
    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    deps.get_game_or_404(game_id, session)
    service = DecisionService(session, game_id)
    player = _get_active_player(session, service, user_id)
    try:
        result = service.fire_fighting_offer_respond(player.game_player_id, body.accept)
        session.commit()
        await events.broadcast_game_event(
            game_id, "game_state_changed",
            {"reason": "fire_fighting_offer_resolved", "result": result},
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/decisions/expense")
async def expense_acknowledge(
    game_id: int,
    body: ExpenseRequest = ExpenseRequest(),
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Acknowledge expense payment, optionally buying the immunity card."""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    deps.get_game_or_404(game_id, session)
    service = DecisionService(session, game_id)
    player = _get_active_player(session, service, user_id)

    try:
        result = service.expense_acknowledge(player.game_player_id,
                                             buy_card=body.buy_card,
                                             option=body.option)
        session.commit()

        await events.broadcast_game_event(
            game_id, "game_state_changed",
            {"reason": "expense_acknowledged", "result": result}
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/decisions/acknowledge")
async def acknowledge_action(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Generic acknowledge for informational pending actions (expense, drought, flood, etc.)."""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    deps.get_game_or_404(game_id, session)
    service = DecisionService(session, game_id)
    player = _get_active_player(session, service, user_id)

    try:
        result = service.acknowledge(player.game_player_id)
        session.commit()

        await events.broadcast_game_event(
            game_id, "game_state_changed",
            {"reason": "action_acknowledged", "action_type": result.get("action_type")}
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Helpers ──────────────────────────────────────────────────────────

def _get_active_player(session: Session, service: DecisionService, user_id: int):
    """Verify the authenticated user owns the active player for the pending action."""
    pending = service.get_pending_action()
    if not pending:
        raise HTTPException(status_code=400, detail="No pending action")

    active_player = session.query(models.GamePlayer).filter_by(
        game_player_id=pending.active_player_id
    ).first()

    if not active_player or active_player.user_id != user_id:
        raise HTTPException(status_code=403, detail="This decision belongs to another player")

    return active_player
