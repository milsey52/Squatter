# app/api/routes/bankruptcy.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from app.api import deps
from app import models
from app.services.bankruptcy_service import BankruptcyService
from app.api.routes.events import broadcast_game_event

router = APIRouter(prefix="/games", tags=["bankruptcy"])


@router.get("/{game_id}/debt-status")
def get_debt_status(
    game_id: int,
    player_id: int,
    db: Session = Depends(deps.get_session)
):
    """Get current player's debt state if any."""
    bankruptcy_service = BankruptcyService(db, game_id)
    debt = bankruptcy_service.get_pending_debt(player_id)

    if not debt:
        return {"has_debt": False}

    # Get creditor name
    creditor_name = "The Bank"
    if debt.creditor_player_id:
        creditor = db.query(models.GamePlayer).filter(
            models.GamePlayer.game_player_id == debt.creditor_player_id
        ).first()
        if creditor:
            creditor_name = creditor.player_name

    # Get asset name if applicable
    asset_name = None
    if debt.asset_id:
        asset = db.query(models.Asset).join(models.Space).filter(
            models.Asset.asset_id == debt.asset_id
        ).first()
        if asset:
            space = db.query(models.Space).filter(
                models.Space.space_id == asset.space_id
            ).first()
            asset_name = space.name if space else None

    return {
        "has_debt": True,
        "debt_state_id": debt.debt_state_id,
        "amount": debt.debt_amount,
        "reason": debt.debt_reason,
        "creditor_name": creditor_name,
        "creditor_id": debt.creditor_player_id,
        "asset_name": asset_name,
        "created_at": debt.created_at.isoformat() if debt.created_at else None
    }


@router.get("/{game_id}/liquidation-preview")
def get_liquidation_preview(
    game_id: int,
    player_id: int,
    db: Session = Depends(deps.get_session)
):
    """Calculate how much player can raise by selling assets."""
    bankruptcy_service = BankruptcyService(db, game_id)
    preview = bankruptcy_service.calculate_liquidation_value(player_id)
    return preview


@router.post("/{game_id}/bankruptcy/resign")
async def resign_from_game(
    game_id: int,
    player_id: int,
    turn_id: Optional[int] = None,
    db: Session = Depends(deps.get_session)
):
    """Player resigns from game - removes player and returns assets to bank."""
    bankruptcy_service = BankruptcyService(db, game_id)

    # Verify player exists and is active
    player = db.query(models.GamePlayer).filter(
        models.GamePlayer.game_player_id == player_id
    ).first()

    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found"
        )

    if not player.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Player is already inactive"
        )

    # Process resignation
    result = bankruptcy_service.resign_player(player_id, turn_id)
    db.commit()

    # Broadcast resignation event
    await broadcast_game_event(game_id, "player_resigned", {
        "player_id": player_id,
        "player_name": player.player_name,
        "game_over": result["game_over"]
    })

    # If game is over, broadcast game over event
    if result["game_over"]:
        winner = db.query(models.GamePlayer).filter(
            models.GamePlayer.game_player_id == result["winner_id"]
        ).first()

        await broadcast_game_event(game_id, "game_over", {
            "winner_id": result["winner_id"],
            "winner_name": winner.player_name if winner else None
        })

    return result


@router.post("/{game_id}/bankruptcy/resolve-debt")
async def resolve_debt(
    game_id: int,
    debt_state_id: int,
    turn_id: Optional[int] = None,
    db: Session = Depends(deps.get_session)
):
    """Process payment for a debt after player has liquidated assets."""
    bankruptcy_service = BankruptcyService(db, game_id)

    # Get debt details before resolving
    debt = db.query(models.DebtState).filter(
        models.DebtState.debt_state_id == debt_state_id
    ).first()

    if not debt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Debt not found"
        )

    if debt.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debt is not in pending status"
        )

    # Attempt to resolve debt
    success = bankruptcy_service.resolve_debt(debt_state_id, turn_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Insufficient funds to resolve debt"
        )

    db.commit()

    # Broadcast debt resolved event
    await broadcast_game_event(game_id, "debt_resolved", {
        "debtor_id": debt.debtor_player_id,
        "creditor_id": debt.creditor_player_id,
        "amount": debt.debt_amount
    })

    return {"success": True, "message": "Debt resolved successfully"}


@router.post("/{game_id}/bankruptcy/sell-jail-card")
def sell_jail_card(
    game_id: int,
    player_id: int,
    card_draw_id: int,
    turn_id: Optional[int] = None,
    db: Session = Depends(deps.get_session)
):
    """Sell a Get Out of Jail Free card back to bank for $500."""
    bankruptcy_service = BankruptcyService(db, game_id)

    success = bankruptcy_service.sell_jail_card(player_id, card_draw_id, turn_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to sell card - card not found or not retainable"
        )

    db.commit()

    return {"success": True, "amount_received": 500}
