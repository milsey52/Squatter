from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_
from pydantic import BaseModel
from typing import List
from app.api import deps, auth
from app import models
from app.services.ledger_service import LedgerService

router = APIRouter()


@router.get("/properties/all")
def get_all_properties(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Get all properties with their ownership information for a game."""
    user_id, token_game_id = auth_data

    # Verify the token's game_id matches the requested game_id
    if token_game_id != game_id:
        raise HTTPException(
            status_code=403,
            detail="Session token is for a different game"
        )

    # Verify game exists
    deps.get_game_or_404(game_id, session)

    # Get all assets (properties, transport, utilities) with their ownership
    properties = (
        session.query(
            models.Asset.asset_id,
            models.Asset.purchase_price,
            models.Space.name,
            models.Space.space_type,
            models.Space.group_id,
            models.AssetState.owner_game_player_id,
            models.GamePlayer.player_name.label('owner_name'),
            models.AssetState.is_mortgaged,
            models.AssetState.improvement_level,
            models.AssetState.has_hotel,
            models.Space.board_index
        )
        .join(models.Space, models.Asset.space_id == models.Space.space_id)
        .outerjoin(
            models.AssetState,
            and_(
                models.AssetState.asset_id == models.Asset.asset_id,
                models.AssetState.game_id == game_id
            )
        )
        .outerjoin(
            models.GamePlayer,
            models.AssetState.owner_game_player_id == models.GamePlayer.game_player_id
        )
        .filter(
            models.Space.space_type.in_(['property', 'transport', 'utility'])
        )
        .order_by(models.Space.board_index)
        .all()
    )

    return {
        "properties": [
            {
                "asset_id": p.asset_id,
                "name": p.name,
                "purchase_price": p.purchase_price,
                "space_type": p.space_type,
                "group_id": p.group_id,
                "owner_name": p.owner_name,
                "is_mortgaged": p.is_mortgaged or False,
                "improvement_level": p.improvement_level or 0,
                "has_hotel": p.has_hotel or False,
                "board_index": p.board_index
            }
            for p in properties
        ]
    }


class ImprovePropertyRequest(BaseModel):
    improvement_type: str  # "house" or "hotel"


class UnimprovePropertyRequest(BaseModel):
    improvement_type: str  # "house" or "hotel"


def get_property_group(session: Session, asset_id: int) -> List[dict]:
    """
    Get all assets in the same property group.
    Group is determined by matching purchase_price, rent structure, and asset_type='property'
    """
    # Get the asset info
    asset = session.query(models.Asset).filter_by(asset_id=asset_id).first()
    if not asset or asset.asset_type != 'property':
        return []

    # Find all properties with the same purchase price and rent structure
    # This identifies properties in the same color group
    group_assets = (
        session.query(models.Asset, models.Space.name)
        .join(models.Space, models.Asset.space_id == models.Space.space_id)
        .filter(
            models.Asset.asset_type == 'property',
            models.Asset.purchase_price == asset.purchase_price,
            models.Asset.rent_house_1 == asset.rent_house_1,
            models.Asset.rent_hotel == asset.rent_hotel
        )
        .all()
    )

    return [{"asset_id": a.asset_id, "name": name} for a, name in group_assets]


def get_house_cost(asset: models.Asset) -> int:
    """Determine house cost from CSV data - stored in asset table or derived"""
    # In the CSV, house costs are in column 13 (House EA)
    # For now, we'll derive from purchase price as a reasonable default
    price_to_cost = {
        600: 600,
        1000: 1000,
        1200: 1000,
        1400: 1400,
        1600: 1400,
        1800: 1800,
        2000: 1800,
        2200: 1800,
        2400: 2000,
        2600: 2000,
        2800: 2000,
    }
    return price_to_cost.get(asset.purchase_price, 1000)


def get_hotel_cost(asset: models.Asset) -> int:
    """Determine hotel cost - typically same as house cost in this game"""
    return get_house_cost(asset)


@router.get("/properties")
def get_player_properties_detailed(
    game_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Get detailed property information for the current player including monopoly status"""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    # Get player
    player = session.query(models.GamePlayer).filter_by(
        game_id=game_id,
        user_id=user_id
    ).first()

    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # Get all properties owned by player
    owned_assets = (
        session.query(models.Asset, models.AssetState, models.Space.name)
        .join(models.AssetState, models.Asset.asset_id == models.AssetState.asset_id)
        .join(models.Space, models.Asset.space_id == models.Space.space_id)
        .filter(
            models.AssetState.game_id == game_id,
            models.AssetState.owner_game_player_id == player.game_player_id,
            models.Asset.asset_type == 'property'
        )
        .all()
    )

    # Group properties by purchase_price/rent structure
    property_groups = {}

    for asset, state, name in owned_assets:
        group_key = f"{asset.purchase_price}_{asset.rent_house_1}"

        if group_key not in property_groups:
            # Get all properties in this group
            group_assets = get_property_group(session, asset.asset_id)

            # Check if player owns all in group (monopoly)
            owned_in_group = [a.asset_id for a in [ast for ast, st, n in owned_assets
                             if f"{ast.purchase_price}_{ast.rent_house_1}" == group_key]]
            has_monopoly = len(owned_in_group) == len(group_assets)

            # Check if any in group are mortgaged
            any_mortgaged = any(st.is_mortgaged for ast, st, n in owned_assets
                               if f"{ast.purchase_price}_{ast.rent_house_1}" == group_key)

            # Check if any in group have improvements
            any_improvements = any(
                (st.improvement_level > 0 or st.has_hotel)
                for ast, st, n in owned_assets
                if f"{ast.purchase_price}_{ast.rent_house_1}" == group_key
            )

            property_groups[group_key] = {
                "group_name": f"${asset.purchase_price} Group",
                "properties": [],
                "has_monopoly": has_monopoly,
                "any_mortgaged": any_mortgaged,
                "any_improvements": any_improvements,
                "total_in_group": len(group_assets),
                "house_cost": get_house_cost(asset),
                "hotel_cost": get_hotel_cost(asset)
            }

        current_rent = asset.rent_base
        if state.has_hotel:
            current_rent = asset.rent_hotel
        elif state.improvement_level > 0:
            rent_map = {
                1: asset.rent_house_1,
                2: asset.rent_house_2,
                3: asset.rent_house_3,
                4: asset.rent_house_4
            }
            current_rent = rent_map.get(state.improvement_level, asset.rent_base)
        elif property_groups[group_key]["has_monopoly"] and not state.is_mortgaged:
            # Monopoly with no improvements gets double rent
            current_rent = asset.rent_group or (asset.rent_base * 2)

        property_groups[group_key]["properties"].append({
            "asset_id": asset.asset_id,
            "name": name,
            "improvement_level": state.improvement_level,
            "has_hotel": state.has_hotel,
            "is_mortgaged": state.is_mortgaged,
            "current_rent": current_rent,
            "can_improve": (
                property_groups[group_key]["has_monopoly"] and
                not property_groups[group_key]["any_mortgaged"] and
                not state.is_mortgaged
            )
        })

    return {"groups": list(property_groups.values())}


@router.post("/properties/{asset_id}/improve")
async def improve_property(
    game_id: int,
    asset_id: int,
    request: ImprovePropertyRequest,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Buy a house or upgrade to hotel on a property"""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    # Get player
    player = session.query(models.GamePlayer).filter_by(
        game_id=game_id,
        user_id=user_id
    ).first()

    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # Get asset and state
    asset = session.query(models.Asset).filter_by(asset_id=asset_id).first()
    asset_state = session.query(models.AssetState).filter_by(
        game_id=game_id,
        asset_id=asset_id
    ).first()

    if not asset or not asset_state:
        raise HTTPException(status_code=404, detail="Property not found")

    if asset.asset_type != 'property':
        raise HTTPException(status_code=400, detail="Can only improve properties")

    # Verify ownership
    if asset_state.owner_game_player_id != player.game_player_id:
        raise HTTPException(status_code=403, detail="You don't own this property")

    # Check if mortgaged
    if asset_state.is_mortgaged:
        raise HTTPException(status_code=400, detail="Cannot improve mortgaged property")

    # Get all properties in the group
    group_assets = get_property_group(session, asset_id)
    group_asset_ids = [a["asset_id"] for a in group_assets]

    # Check monopoly ownership
    owned_in_group = session.query(models.AssetState).filter(
        models.AssetState.game_id == game_id,
        models.AssetState.asset_id.in_(group_asset_ids),
        models.AssetState.owner_game_player_id == player.game_player_id
    ).count()

    if owned_in_group != len(group_assets):
        raise HTTPException(status_code=400, detail="Must own all properties in color group (monopoly)")

    # Check if any property in group is mortgaged
    any_mortgaged = session.query(models.AssetState).filter(
        models.AssetState.game_id == game_id,
        models.AssetState.asset_id.in_(group_asset_ids),
        models.AssetState.is_mortgaged == True
    ).first()

    if any_mortgaged:
        raise HTTPException(status_code=400, detail="Cannot improve while any property in group is mortgaged")

    # Get improvement levels of all properties in group
    group_states = session.query(models.AssetState).filter(
        models.AssetState.game_id == game_id,
        models.AssetState.asset_id.in_(group_asset_ids)
    ).all()

    # Calculate costs
    house_cost = get_house_cost(asset)
    hotel_cost = get_hotel_cost(asset)

    if request.improvement_type == "house":
        # Check if already has hotel
        if asset_state.has_hotel:
            raise HTTPException(status_code=400, detail="Property already has hotel")

        # Check if at max houses
        if asset_state.improvement_level >= 4:
            raise HTTPException(status_code=400, detail="Property has maximum houses (upgrade to hotel instead)")

        # Check even building rule - can't be more than 1 house ahead
        min_houses = min(s.improvement_level for s in group_states if not s.has_hotel)
        if asset_state.improvement_level > min_houses:
            raise HTTPException(status_code=400, detail="Must build houses evenly across color group")

        # Check player has enough cash
        ledger = LedgerService(session, game_id)
        balance = ledger.player_balance(player.game_player_id)

        if balance < house_cost:
            raise HTTPException(status_code=400, detail=f"Insufficient funds. Need ${house_cost}, have ${balance}")

        # Build house
        asset_state.improvement_level += 1

        # Get current turn
        current_turn = session.query(models.Turn).filter_by(
            game_id=game_id
        ).order_by(models.Turn.turn_id.desc()).first()
        turn_id = current_turn.turn_id if current_turn else None

        # Charge player
        ledger.pay_bank(
            player=player,
            amount=house_cost,
            txn_type="house_purchase",
            turn_id=turn_id,
            asset_id=asset_id,
            notes=f"Bought house on property"
        )

        session.commit()

        return {
            "status": "success",
            "improvement_level": asset_state.improvement_level,
            "cost": house_cost
        }

    elif request.improvement_type == "hotel":
        # Must have 4 houses first
        if asset_state.improvement_level != 4:
            raise HTTPException(status_code=400, detail="Must have 4 houses before buying hotel")

        # Check player has enough cash
        ledger = LedgerService(session, game_id)
        balance = ledger.player_balance(player.game_player_id)

        if balance < hotel_cost:
            raise HTTPException(status_code=400, detail=f"Insufficient funds. Need ${hotel_cost}, have ${balance}")

        # Build hotel (remove 4 houses, add hotel)
        asset_state.improvement_level = 0
        asset_state.has_hotel = True

        # Get current turn
        current_turn = session.query(models.Turn).filter_by(
            game_id=game_id
        ).order_by(models.Turn.turn_id.desc()).first()
        turn_id = current_turn.turn_id if current_turn else None

        # Charge player
        ledger.pay_bank(
            player=player,
            amount=hotel_cost,
            txn_type="hotel_purchase",
            turn_id=turn_id,
            asset_id=asset_id,
            notes=f"Bought hotel on property"
        )

        session.commit()

        return {
            "status": "success",
            "has_hotel": True,
            "cost": hotel_cost
        }

    else:
        raise HTTPException(status_code=400, detail="Invalid improvement type")


@router.post("/properties/{asset_id}/unimprove")
async def unimprove_property(
    game_id: int,
    asset_id: int,
    request: UnimprovePropertyRequest,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Sell a house or downgrade from hotel"""
    user_id, token_game_id = auth_data

    if token_game_id != game_id:
        raise HTTPException(status_code=403, detail="Session token is for a different game")

    # Get player
    player = session.query(models.GamePlayer).filter_by(
        game_id=game_id,
        user_id=user_id
    ).first()

    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # Get asset and state
    asset = session.query(models.Asset).filter_by(asset_id=asset_id).first()
    asset_state = session.query(models.AssetState).filter_by(
        game_id=game_id,
        asset_id=asset_id
    ).first()

    if not asset or not asset_state:
        raise HTTPException(status_code=404, detail="Property not found")

    # Verify ownership
    if asset_state.owner_game_player_id != player.game_player_id:
        raise HTTPException(status_code=403, detail="You don't own this property")

    # Get all properties in the group
    group_assets = get_property_group(session, asset_id)
    group_asset_ids = [a["asset_id"] for a in group_assets]

    # Get improvement levels of all properties in group
    group_states = session.query(models.AssetState).filter(
        models.AssetState.game_id == game_id,
        models.AssetState.asset_id.in_(group_asset_ids)
    ).all()

    # Calculate refund (50% of cost)
    house_cost = get_house_cost(asset)
    hotel_cost = get_hotel_cost(asset)

    ledger = LedgerService(session, game_id)

    # Get current turn
    current_turn = session.query(models.Turn).filter_by(
        game_id=game_id
    ).order_by(models.Turn.turn_id.desc()).first()
    turn_id = current_turn.turn_id if current_turn else None

    if request.improvement_type == "hotel":
        if not asset_state.has_hotel:
            raise HTTPException(status_code=400, detail="Property doesn't have a hotel")

        # Downgrade hotel to 4 houses
        asset_state.has_hotel = False
        asset_state.improvement_level = 4

        refund = hotel_cost // 2

        ledger.receive_from_bank(
            player=player,
            amount=refund,
            txn_type="hotel_sale",
            turn_id=turn_id,
            asset_id=asset_id,
            notes=f"Sold hotel (50% refund)"
        )

        session.commit()

        return {
            "status": "success",
            "has_hotel": False,
            "improvement_level": 4,
            "refund": refund
        }

    elif request.improvement_type == "house":
        if asset_state.improvement_level == 0:
            raise HTTPException(status_code=400, detail="Property has no houses")

        # Check even building rule - can't be more than 1 house behind
        max_houses = max(s.improvement_level for s in group_states if not s.has_hotel)
        if asset_state.improvement_level < max_houses:
            raise HTTPException(status_code=400, detail="Must sell houses evenly across color group")

        # Sell one house
        asset_state.improvement_level -= 1

        refund = house_cost // 2

        ledger.receive_from_bank(
            player=player,
            amount=refund,
            txn_type="house_sale",
            turn_id=turn_id,
            asset_id=asset_id,
            notes=f"Sold house (50% refund)"
        )

        session.commit()

        return {
            "status": "success",
            "improvement_level": asset_state.improvement_level,
            "refund": refund
        }

    else:
        raise HTTPException(status_code=400, detail="Invalid improvement type")
