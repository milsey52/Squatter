# app/api/routes/station.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from app.api import deps, auth
from app.api.routes import events
from app import models
from app.services.station_service import StationService
from app.services.ledger_service import LedgerService
from app.services.bankruptcy_service import BankruptcyService
from app.constants import (
    HAYSTACK_COST, HAYSTACK_SELL_PRICE,
    STUD_RAM_SELL_PRICE, EMERGENCY_SELL_PRICE_PER_PEN,
    haystack_buy_price,
)

router = APIRouter()


class UpgradePaddockRequest(BaseModel):
    paddock_id: int
    target_type: str  # "improved" or "irrigated"


class MortgagePaddockRequest(BaseModel):
    paddock_id: int


class SellSheepRequest(BaseModel):
    pens: int


class MoveSheepRequest(BaseModel):
    from_paddock_id: int
    to_paddock_id: int
    pens: int


class SellStudRamRequest(BaseModel):
    space_id: int


@router.get("")
def get_my_station(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Get the authenticated player's station summary."""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    player = session.query(models.GamePlayer).filter_by(
        game_id=game_id, user_id=user_id
    ).first()

    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    station_svc = StationService(session, game_id)
    ledger_svc = LedgerService(session, game_id)

    summary = station_svc.get_station_summary(player.game_player_id)
    summary["balance"] = ledger_svc.player_balance(player.game_player_id)
    return summary


@router.post("/upgrade-paddock")
async def upgrade_paddock(
    game_id: int,
    body: UpgradePaddockRequest,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Upgrade a paddock (natural->improved or improved->irrigated)."""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    player = session.query(models.GamePlayer).filter_by(
        game_id=game_id, user_id=user_id
    ).first()

    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # Rule: a Player can only purchase Improved / Irrigated pasture on their own turn.
    game = deps.get_game_or_404(game_id, session)
    if game.current_game_player_id != player.game_player_id:
        raise HTTPException(status_code=400,
                            detail="You can only purchase Improved/Irrigated pasture on your own turn")

    # Rule: a Player in drought cannot upgrade paddocks.
    if player.is_in_drought:
        raise HTTPException(status_code=400,
                            detail="Cannot upgrade paddocks while in drought")

    station_svc = StationService(session, game_id)
    ledger_svc = LedgerService(session, game_id)

    # Get paddock and validate ownership
    paddock = session.query(models.Paddock).filter_by(
        paddock_id=body.paddock_id,
        owner_game_player_id=player.game_player_id
    ).first()

    if not paddock:
        raise HTTPException(status_code=404, detail="Paddock not found or not owned by you")

    # Get cost and validate
    from app.constants import IMPROVED_PASTURE_COST, IRRIGATED_PASTURE_COST

    if body.target_type == "improved":
        info = station_svc.can_upgrade_to_improved(player.game_player_id)
        if not info["can_upgrade"] or paddock.paddock_number not in info["available_paddocks"]:
            raise HTTPException(status_code=400, detail="Cannot upgrade to improved (must be natural with stock)")
        cost = IMPROVED_PASTURE_COST
    elif body.target_type == "irrigated":
        info = station_svc.can_upgrade_to_irrigated(player.game_player_id)
        if not info["can_upgrade"]:
            raise HTTPException(status_code=400, detail=f"Cannot upgrade to irrigated (need all {info['required']} paddocks improved first, have {info['improved_count']})")
        cost = IRRIGATED_PASTURE_COST
    else:
        raise HTTPException(status_code=400, detail="Invalid target type")

    balance = ledger_svc.player_balance(player.game_player_id)
    if balance < cost:
        raise HTTPException(status_code=400, detail=f"Insufficient funds: need ${cost}, have ${balance}")

    # Get current turn
    turn = session.query(models.Turn).filter_by(
        game_id=game_id
    ).order_by(models.Turn.turn_id.desc()).first()
    turn_id = turn.turn_id if turn else None

    ledger_svc.pay_bank(player, cost, "paddock_upgrade", turn_id,
                        notes=f"Upgraded paddock {paddock.paddock_number} to {body.target_type}")
    station_svc.upgrade_paddock(player.game_player_id, paddock.paddock_number, body.target_type)
    session.commit()

    await events.broadcast_game_event(
        game_id, "game_state_changed",
        {"reason": "paddock_upgraded", "player_id": player.game_player_id}
    )

    return {"status": "upgraded", "paddock_number": paddock.paddock_number, "new_type": body.target_type}


@router.post("/mortgage-paddock")
async def mortgage_paddock(
    game_id: int,
    body: MortgagePaddockRequest,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Mortgage a paddock to receive cash."""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    player = session.query(models.GamePlayer).filter_by(
        game_id=game_id, user_id=user_id
    ).first()

    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    station_svc = StationService(session, game_id)
    ledger_svc = LedgerService(session, game_id)

    paddock = session.query(models.Paddock).filter_by(
        paddock_id=body.paddock_id,
        owner_game_player_id=player.game_player_id
    ).first()

    if not paddock:
        raise HTTPException(status_code=404, detail="Paddock not found or not owned by you")

    if paddock.is_mortgaged:
        raise HTTPException(status_code=400, detail="Paddock is already mortgaged")

    # Rule: mortgaging is only allowed when the player has been reduced to 8 Pens of Sheep or less.
    total_pens = station_svc.get_total_pens(player.game_player_id)
    if total_pens > 8:
        raise HTTPException(status_code=400,
                            detail=f"Mortgage only allowed when reduced to 8 pens or less (you have {total_pens})")

    mortgage_value = station_svc.mortgage_paddock(player.game_player_id, paddock.paddock_number)

    turn = session.query(models.Turn).filter_by(
        game_id=game_id
    ).order_by(models.Turn.turn_id.desc()).first()
    turn_id = turn.turn_id if turn else None

    ledger_svc.receive_from_bank(player, mortgage_value, "mortgage", turn_id,
                                  notes=f"Mortgaged paddock {paddock.paddock_number}")
    BankruptcyService(session, game_id).clear_debt_pending_if_solvent(player.game_player_id)
    session.commit()

    await events.broadcast_game_event(
        game_id, "game_state_changed",
        {"reason": "paddock_mortgaged", "player_id": player.game_player_id}
    )

    return {"status": "mortgaged", "amount_received": mortgage_value}


@router.post("/unmortgage-paddock")
async def unmortgage_paddock(
    game_id: int,
    body: MortgagePaddockRequest,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Pay off mortgage on a paddock."""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    player = session.query(models.GamePlayer).filter_by(
        game_id=game_id, user_id=user_id
    ).first()

    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    station_svc = StationService(session, game_id)
    ledger_svc = LedgerService(session, game_id)

    paddock = session.query(models.Paddock).filter_by(
        paddock_id=body.paddock_id,
        owner_game_player_id=player.game_player_id
    ).first()

    if not paddock:
        raise HTTPException(status_code=404, detail="Paddock not found or not owned by you")

    if not paddock.is_mortgaged:
        raise HTTPException(status_code=400, detail="Paddock is not mortgaged")

    from app.constants import MORTGAGE_NATURAL, MORTGAGE_IMPROVED, MORTGAGE_IRRIGATED, MORTGAGE_INTEREST_RATE
    mortgage_values = {"natural": MORTGAGE_NATURAL, "improved": MORTGAGE_IMPROVED, "irrigated": MORTGAGE_IRRIGATED}
    base_value = mortgage_values[paddock.paddock_type]
    repay_cost = int(base_value * (1 + MORTGAGE_INTEREST_RATE))

    balance = ledger_svc.player_balance(player.game_player_id)
    if balance < repay_cost:
        raise HTTPException(status_code=400, detail=f"Insufficient funds: need ${repay_cost}, have ${balance}")

    turn = session.query(models.Turn).filter_by(
        game_id=game_id
    ).order_by(models.Turn.turn_id.desc()).first()
    turn_id = turn.turn_id if turn else None

    ledger_svc.pay_bank(player, repay_cost, "unmortgage", turn_id,
                        notes=f"Unmortgaged paddock {paddock.paddock_number}")
    station_svc.unmortgage_paddock(player.game_player_id, paddock.paddock_number)
    # Redeeming the last mortgage on a fully-irrigated, 30-pen station = win.
    station_svc.declare_winner_if_eligible(player.game_player_id, turn_id)
    session.commit()

    await events.broadcast_game_event(
        game_id, "game_state_changed",
        {"reason": "paddock_unmortgaged", "player_id": player.game_player_id}
    )

    return {"status": "unmortgaged", "cost": repay_cost}


@router.post("/sell-to-bank")
async def sell_sheep_to_bank(
    game_id: int,
    body: SellSheepRequest,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Emergency sell sheep to bank at $400/pen."""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    player = session.query(models.GamePlayer).filter_by(
        game_id=game_id, user_id=user_id
    ).first()

    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    station_svc = StationService(session, game_id)
    ledger_svc = LedgerService(session, game_id)

    total_pens = station_svc.get_total_pens(player.game_player_id)
    if body.pens > total_pens:
        raise HTTPException(status_code=400, detail=f"Cannot sell more than you have ({total_pens} pens)")

    if body.pens <= 0:
        raise HTTPException(status_code=400, detail="Must sell at least 1 pen")

    station_svc.sell_sheep(player.game_player_id, body.pens)
    income = body.pens * EMERGENCY_SELL_PRICE_PER_PEN

    turn = session.query(models.Turn).filter_by(
        game_id=game_id
    ).order_by(models.Turn.turn_id.desc()).first()
    turn_id = turn.turn_id if turn else None

    ledger_svc.receive_from_bank(player, income, "emergency_sale", turn_id,
                                  notes=f"Emergency sold {body.pens} pens at ${EMERGENCY_SELL_PRICE_PER_PEN}/pen")
    BankruptcyService(session, game_id).clear_debt_pending_if_solvent(player.game_player_id)
    session.commit()

    await events.broadcast_game_event(
        game_id, "game_state_changed",
        {"reason": "sheep_sold", "player_id": player.game_player_id}
    )

    return {"status": "sold", "pens": body.pens, "income": income}


@router.post("/buy-haystack")
async def buy_haystack(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Buy a haystack for drought protection."""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    player = session.query(models.GamePlayer).filter_by(
        game_id=game_id, user_id=user_id
    ).first()

    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    if player.has_haystack:
        raise HTTPException(status_code=400, detail="Already have a haystack")

    ledger_svc = LedgerService(session, game_id)
    balance = ledger_svc.player_balance(player.game_player_id)

    cost = haystack_buy_price(player)
    if balance < cost:
        raise HTTPException(status_code=400, detail=f"Insufficient funds: need ${cost}, have ${balance}")

    turn = session.query(models.Turn).filter_by(
        game_id=game_id
    ).order_by(models.Turn.turn_id.desc()).first()
    turn_id = turn.turn_id if turn else None

    notes = "Bought haystack" + (" (drought premium)" if player.is_in_drought else "")
    ledger_svc.pay_bank(player, cost, "haystack_purchase", turn_id, notes=notes)
    player.has_haystack = True

    # Auto-resolve a standalone haystack_offer pending action so the modal closes.
    standalone = session.query(models.PendingAction).filter_by(
        game_id=game_id,
        active_player_id=player.game_player_id,
        action_type="haystack_offer",
        resolved_at=None,
    ).first()
    if standalone:
        from sqlalchemy import func as sa_func
        standalone.resolved_at = sa_func.now()

    session.commit()

    await events.broadcast_game_event(
        game_id, "game_state_changed",
        {"reason": "haystack_bought", "player_id": player.game_player_id}
    )

    return {"status": "purchased", "cost": cost}


@router.post("/sell-haystack")
async def sell_haystack(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Sell haystack back."""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    player = session.query(models.GamePlayer).filter_by(
        game_id=game_id, user_id=user_id
    ).first()

    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    if not player.has_haystack:
        raise HTTPException(status_code=400, detail="No haystack to sell")

    ledger_svc = LedgerService(session, game_id)

    turn = session.query(models.Turn).filter_by(
        game_id=game_id
    ).order_by(models.Turn.turn_id.desc()).first()
    turn_id = turn.turn_id if turn else None

    ledger_svc.receive_from_bank(player, HAYSTACK_SELL_PRICE, "haystack_sale", turn_id,
                                  notes="Sold haystack")
    player.has_haystack = False
    player.haystack_used = False
    BankruptcyService(session, game_id).clear_debt_pending_if_solvent(player.game_player_id)
    session.commit()

    await events.broadcast_game_event(
        game_id, "game_state_changed",
        {"reason": "haystack_sold", "player_id": player.game_player_id}
    )

    return {"status": "sold", "income": HAYSTACK_SELL_PRICE}


@router.post("/sell-stud-ram")
async def sell_stud_ram(
    game_id: int,
    body: SellStudRamRequest,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Sell a stud ram back to the bank."""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    player = session.query(models.GamePlayer).filter_by(
        game_id=game_id, user_id=user_id
    ).first()

    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    ram_state = session.query(models.StudRamState).filter_by(
        game_id=game_id,
        space_id=body.space_id,
        owner_game_player_id=player.game_player_id
    ).first()

    if not ram_state:
        raise HTTPException(status_code=404, detail="Stud ram not found or not owned by you")

    ledger_svc = LedgerService(session, game_id)

    turn = session.query(models.Turn).filter_by(
        game_id=game_id
    ).order_by(models.Turn.turn_id.desc()).first()
    turn_id = turn.turn_id if turn else None

    ledger_svc.receive_from_bank(player, STUD_RAM_SELL_PRICE, "stud_ram_sale", turn_id,
                                  notes="Sold stud ram")
    ram_state.owner_game_player_id = None
    ram_state.is_available = True
    BankruptcyService(session, game_id).clear_debt_pending_if_solvent(player.game_player_id)
    session.commit()

    await events.broadcast_game_event(
        game_id, "game_state_changed",
        {"reason": "stud_ram_sold", "player_id": player.game_player_id}
    )

    return {"status": "sold", "income": STUD_RAM_SELL_PRICE}


@router.post("/move-sheep")
async def move_sheep(
    game_id: int,
    body: MoveSheepRequest,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session),
):
    """Move sheep pens between two paddocks owned by the same player.
    Use to redistribute stock onto upgraded pasture (e.g., Natural→Improved
    after a property improvement) without exceeding carrying capacity."""
    user_id, token_game_id = auth_data
    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    player = session.query(models.GamePlayer).filter_by(
        game_id=game_id, user_id=user_id
    ).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    station_svc = StationService(session, game_id)
    try:
        result = station_svc.move_sheep(
            player.game_player_id,
            body.from_paddock_id,
            body.to_paddock_id,
            body.pens,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    session.commit()
    await events.broadcast_game_event(
        game_id, "game_state_changed",
        {"reason": "sheep_moved", "player_id": player.game_player_id, "result": result},
    )
    return {"status": "moved", **result}
