from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_session
from app.api import auth
from app import models

router = APIRouter()

@router.get("/games/{game_id}/players/{player_id}/assets")
def get_player_assets(game_id: int, player_id: int, session: Session = Depends(get_session)):
    query = (
        session.query(models.Asset, models.AssetState)
        .join(models.AssetState, models.Asset.asset_id == models.AssetState.asset_id)
        .filter(
            models.AssetState.game_id == game_id,
            models.AssetState.owner_game_player_id == player_id
        )
        .all()
    )
    result = []
    for asset, state in query:
        result.append({
            "asset_id": asset.asset_id,
            "name": asset.space_id,  # or fetch name from Space
            "asset_type": asset.asset_type,
            "group_id": asset.group_id if hasattr(asset, "group_id") else None,
            "is_mortgaged": state.is_mortgaged,
            "improvement_level": state.improvement_level,
            "has_hotel": state.has_hotel,
        })
    return result

@router.get("/games/{game_id}/player_assets")
def get_all_player_assets(game_id: int, session: Session = Depends(get_session)):
    assets_query = (
        session.query(
            models.AssetState.owner_game_player_id,
            models.Asset.asset_id,
            models.Asset.asset_type,
            models.Asset.space_id,
            models.AssetState.is_mortgaged,
            models.AssetState.improvement_level,
            models.AssetState.has_hotel,
            models.Space.name.label("property_name"),
            models.Space.group_id,
            models.Asset.purchase_price,
            models.Asset.mortgage_value,
        )
        .join(models.Asset, models.Asset.asset_id == models.AssetState.asset_id)
        .join(models.Space, models.Asset.space_id == models.Space.space_id)
        .filter(models.AssetState.game_id == game_id)
        .filter(models.AssetState.owner_game_player_id.isnot(None))
    )
    out = {}
    for row in assets_query:
        owner = str(row.owner_game_player_id)
        out.setdefault(owner, []).append({
            "asset_id": row.asset_id,
            "space_id": row.space_id,
            "name": row.property_name,
            "asset_type": row.asset_type,
            "group_id": row.group_id,
            "is_mortgaged": row.is_mortgaged,
            "improvement_level": row.improvement_level,
            "has_hotel": row.has_hotel,
            "purchase_price": row.purchase_price,
            "mortgage_value": row.mortgage_value,
        })
    return out


@router.get("/games/{game_id}/players/worth")
def get_player_worth(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(get_session)
):
    """
    Calculate player's total worth including:
    - Cash balance
    - Property values (purchase price)
    - Improvement values (houses/hotels)
    - Card values
    - Worth before mortgage (full value)
    - Worth after mortgage (if all properties mortgaged)
    """
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    # Find player
    player = session.query(models.GamePlayer).filter_by(
        game_id=game_id,
        user_id=user_id
    ).first()

    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # Get cash balance
    from app.services.ledger_service import LedgerService
    ledger = LedgerService(session, game_id)
    cash_balance = ledger.player_balance(player.game_player_id)

    # Get all owned assets with details
    owned_assets = (
        session.query(models.Asset, models.AssetState, models.Space)
        .join(models.AssetState, models.Asset.asset_id == models.AssetState.asset_id)
        .join(models.Space, models.Asset.space_id == models.Space.space_id)
        .filter(
            models.AssetState.game_id == game_id,
            models.AssetState.owner_game_player_id == player.game_player_id
        )
        .all()
    )

    # Calculate property values
    properties = []
    total_property_value = 0
    total_mortgage_value = 0
    total_improvement_value = 0

    for asset, state, space in owned_assets:
        property_value = asset.purchase_price if not state.is_mortgaged else 0
        mortgage_value = asset.mortgage_value

        # Calculate improvement value
        improvement_value = 0
        if state.has_hotel:
            improvement_value = asset.house_price * 5  # Hotel = 5 houses worth
        elif state.improvement_level > 0:
            improvement_value = asset.house_price * state.improvement_level

        total_property_value += property_value
        total_mortgage_value += mortgage_value
        total_improvement_value += improvement_value

        properties.append({
            "name": space.name,
            "asset_type": asset.asset_type,
            "purchase_price": asset.purchase_price,
            "mortgage_value": asset.mortgage_value,
            "is_mortgaged": state.is_mortgaged,
            "improvement_level": state.improvement_level,
            "has_hotel": state.has_hotel,
            "improvement_value": improvement_value,
            "current_value": property_value + improvement_value
        })

    # Get "Get Out of Jail Free" cards
    jail_cards = (
        session.query(models.CardDraw)
        .join(models.Card)
        .filter(
            models.CardDraw.game_id == game_id,
            models.CardDraw.kept_by_player_id == player.game_player_id,
            models.Card.effect_code == "GET_OUT_OF_JAIL",
            models.CardDraw.discarded_at.is_(None),
        )
        .count()
    )

    # Card value (Get Out of Jail Free card is worth the jail fine it saves)
    from app.constants import JAIL_FINE
    card_value = jail_cards * JAIL_FINE

    # Calculate totals
    total_worth = cash_balance + total_property_value + total_improvement_value + card_value

    # Worth if everything mortgaged (sell improvements, mortgage all properties)
    # When mortgaging, you must sell improvements first (at half price)
    improvement_sell_value = total_improvement_value // 2
    worth_after_mortgage = cash_balance + improvement_sell_value + total_mortgage_value + card_value

    return {
        "cash_balance": cash_balance,
        "properties": properties,
        "total_property_value": total_property_value,
        "total_improvement_value": total_improvement_value,
        "jail_cards": jail_cards,
        "card_value": card_value,
        "total_worth": total_worth,
        "worth_after_mortgage": worth_after_mortgage,
        "summary": {
            "cash": cash_balance,
            "properties": total_property_value,
            "improvements": total_improvement_value,
            "cards": card_value,
            "total": total_worth,
            "if_all_mortgaged": worth_after_mortgage
        }
    }