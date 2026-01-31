from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_session
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