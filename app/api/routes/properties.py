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

    # Get all assets (properties, transport, utilities) with their ownership and asset details
    properties = (
        session.query(
            models.Asset,
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

    # Helper function to check if owner has monopoly
    def has_monopoly(owner_id, group_id, asset_type):
        if not owner_id or not group_id or asset_type != 'property':
            return False

        # Get all properties in the same group
        group_asset_ids = (
            session.query(models.Asset.asset_id)
            .join(models.Space, models.Asset.space_id == models.Space.space_id)
            .filter(
                models.Space.group_id == group_id,
                models.Asset.asset_type == 'property'
            )
            .all()
        )
        group_ids = [aid[0] for aid in group_asset_ids]

        # Count how many are owned by this player (not mortgaged)
        owned_count = (
            session.query(models.AssetState)
            .filter(
                models.AssetState.game_id == game_id,
                models.AssetState.asset_id.in_(group_ids),
                models.AssetState.owner_game_player_id == owner_id,
                models.AssetState.is_mortgaged == False
            )
            .count()
        )

        return owned_count == len(group_ids)

    # Helper function to count owned assets of a type
    def count_owned(owner_id, asset_type):
        if not owner_id:
            return 0
        return (
            session.query(models.AssetState)
            .join(models.Asset, models.Asset.asset_id == models.AssetState.asset_id)
            .filter(
                models.AssetState.game_id == game_id,
                models.AssetState.owner_game_player_id == owner_id,
                models.AssetState.is_mortgaged == False,
                models.Asset.asset_type == asset_type
            )
            .count()
        )

    result_properties = []
    for asset, name, space_type, group_id, owner_id, owner_name, is_mortgaged, improvement_level, has_hotel, board_index in properties:
        # Calculate current rent
        current_rent = 0

        if is_mortgaged:
            current_rent = 0
        elif space_type == 'property':
            if has_hotel:
                current_rent = asset.rent_hotel or 0
            elif improvement_level and improvement_level > 0:
                rent_map = {
                    1: asset.rent_house_1,
                    2: asset.rent_house_2,
                    3: asset.rent_house_3,
                    4: asset.rent_house_4
                }
                current_rent = rent_map.get(improvement_level, asset.rent_base) or 0
            elif has_monopoly(owner_id, group_id, space_type):
                current_rent = asset.rent_group or (asset.rent_base * 2 if asset.rent_base else 0)
            else:
                current_rent = asset.rent_base or 0
        elif space_type == 'transport':
            owned = count_owned(owner_id, 'transport')
            if owned == 1:
                current_rent = asset.rent_base or 0
            elif owned == 2:
                current_rent = asset.rent_tier_2 or asset.rent_base or 0
            elif owned == 3:
                current_rent = asset.rent_tier_3 or asset.rent_tier_2 or asset.rent_base or 0
            elif owned >= 4:
                current_rent = asset.rent_tier_4 or asset.rent_tier_3 or asset.rent_tier_2 or asset.rent_base or 0
        elif space_type == 'utility':
            # For utilities, we can't calculate exact rent without dice roll
            # Show the multiplier instead
            owned = count_owned(owner_id, 'utility')
            if owned == 1:
                current_rent = asset.utility_mult_single or 0  # This is a multiplier, not actual rent
            elif owned >= 2:
                current_rent = asset.utility_mult_double or 0  # This is a multiplier, not actual rent

        result_properties.append({
            "asset_id": asset.asset_id,
            "name": name,
            "purchase_price": asset.purchase_price,
            "space_type": space_type,
            "group_id": group_id,
            "owner_name": owner_name,
            "is_mortgaged": is_mortgaged or False,
            "improvement_level": improvement_level or 0,
            "has_hotel": has_hotel or False,
            "board_index": board_index,
            "current_rent": current_rent
        })

    return {"properties": result_properties}


class ImprovePropertyRequest(BaseModel):
    improvement_type: str  # "house" or "hotel"


class UnimprovePropertyRequest(BaseModel):
    improvement_type: str  # "house" or "hotel"


def get_property_group(session: Session, asset_id: int) -> List[dict]:
    """
    Get all assets in the same property group.
    Group is determined by the group_id in the spaces table.
    """
    # Get the property's space and group_id
    property_asset = session.query(models.Asset).filter_by(asset_id=asset_id).first()
    if not property_asset or property_asset.asset_type != 'property':
        return []

    property_space = session.query(models.Space).filter_by(space_id=property_asset.space_id).first()
    if not property_space or not property_space.group_id:
        return []

    # Get all properties in the same group
    group_assets = (
        session.query(models.Asset, models.Space.name)
        .join(models.Space, models.Asset.space_id == models.Space.space_id)
        .filter(
            models.Space.group_id == property_space.group_id,
            models.Asset.asset_type == 'property'
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

    # Get all assets owned by player (properties, transport, utilities)
    owned_assets = (
        session.query(models.Asset, models.AssetState, models.Space.name, models.Space.group_id, models.Space.space_type)
        .join(models.AssetState, models.Asset.asset_id == models.AssetState.asset_id)
        .join(models.Space, models.Asset.space_id == models.Space.space_id)
        .filter(
            models.AssetState.game_id == game_id,
            models.AssetState.owner_game_player_id == player.game_player_id
        )
        .all()
    )

    # Group properties by group_id, and create separate groups for transport and utilities
    property_groups = {}

    for asset, state, name, group_id, space_type in owned_assets:
        # Handle transport and utilities separately
        if space_type == 'transport':
            group_key = "transport"
        elif space_type == 'utility':
            group_key = "utility"
        elif group_id:
            group_key = f"group_{group_id}"
        else:
            # Handle properties without a group_id - group them separately
            group_key = f"ungrouped_{asset.asset_id}"

        if group_key not in property_groups:
            # Handle transport and utilities differently from properties
            if space_type == 'transport':
                property_groups[group_key] = {
                    "group_name": "Transport Stations",
                    "properties": [],
                    "has_monopoly": False,  # Transport doesn't have monopolies
                    "any_mortgaged": False,
                    "any_improvements": False,
                    "total_in_group": 4,  # There are 4 transport stations
                    "house_cost": 0,
                    "hotel_cost": 0
                }
            elif space_type == 'utility':
                property_groups[group_key] = {
                    "group_name": "Utilities",
                    "properties": [],
                    "has_monopoly": False,  # Utilities don't have monopolies
                    "any_mortgaged": False,
                    "any_improvements": False,
                    "total_in_group": 2,  # There are 2 utilities
                    "house_cost": 0,
                    "hotel_cost": 0
                }
            elif group_id:
                # Get all properties in this color group
                group_assets = get_property_group(session, asset.asset_id)
                group_asset_ids = [a["asset_id"] for a in group_assets]

                # Check if player owns all in group (monopoly)
                owned_in_group = session.query(models.AssetState).filter(
                    models.AssetState.game_id == game_id,
                    models.AssetState.asset_id.in_(group_asset_ids),
                    models.AssetState.owner_game_player_id == player.game_player_id
                ).count()
                has_monopoly = owned_in_group == len(group_assets)

                # Check if any in group are mortgaged
                any_mortgaged = session.query(models.AssetState).filter(
                    models.AssetState.game_id == game_id,
                    models.AssetState.asset_id.in_(group_asset_ids),
                    models.AssetState.is_mortgaged == True
                ).first() is not None

                # Check if any in group have improvements
                any_improvements = session.query(models.AssetState).filter(
                    models.AssetState.game_id == game_id,
                    models.AssetState.asset_id.in_(group_asset_ids),
                    (models.AssetState.improvement_level > 0) | (models.AssetState.has_hotel == True)
                ).first() is not None

                # Get group name and color from property_groups table
                property_group = session.query(models.PropertyGroup).filter_by(group_id=group_id).first()
                group_name = property_group.group_name if property_group else f"Group {group_id}"
                color_hex = property_group.color_hex if property_group else None

                property_groups[group_key] = {
                    "group_name": group_name,
                    "color_hex": color_hex,
                    "properties": [],
                    "has_monopoly": has_monopoly,
                    "any_mortgaged": any_mortgaged,
                    "any_improvements": any_improvements,
                    "total_in_group": len(group_assets),
                    "house_cost": get_house_cost(asset),
                    "hotel_cost": get_hotel_cost(asset)
                }
            else:
                # Handle properties without a group_id (ungrouped properties)
                property_groups[group_key] = {
                    "group_name": name,  # Use property name as group name
                    "properties": [],
                    "has_monopoly": False,  # Ungrouped properties can't have monopoly
                    "any_mortgaged": False,
                    "any_improvements": False,
                    "total_in_group": 1,  # Single property group
                    "house_cost": get_house_cost(asset),
                    "hotel_cost": get_hotel_cost(asset)
                }

        # Calculate current rent based on asset type
        if space_type == 'transport':
            # Transport rent is based on how many owned (already calculated)
            current_rent = asset.rent_base or 0
        elif space_type == 'utility':
            # Utility rent is a multiplier (show base multiplier)
            current_rent = asset.utility_mult_single or 0
        else:
            # Property rent calculation
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
            "mortgage_value": asset.mortgage_value,
            "current_rent": current_rent,
            "can_improve": (
                space_type == 'property' and  # Only properties can be improved
                property_groups[group_key]["has_monopoly"] and
                not property_groups[group_key]["any_mortgaged"] and
                not state.is_mortgaged
            ),
            # Rent progression for properties (null for transport/utilities)
            "rent_base": asset.rent_base if space_type == 'property' else None,
            "rent_group": asset.rent_group if space_type == 'property' else None,
            "rent_house_1": asset.rent_house_1 if space_type == 'property' else None,
            "rent_house_2": asset.rent_house_2 if space_type == 'property' else None,
            "rent_house_3": asset.rent_house_3 if space_type == 'property' else None,
            "rent_house_4": asset.rent_house_4 if space_type == 'property' else None,
            "rent_hotel": asset.rent_hotel if space_type == 'property' else None
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


@router.post("/properties/{asset_id}/mortgage")
async def mortgage_property(
    game_id: int,
    asset_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Mortgage a property to receive cash from the bank"""
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

    # Check if already mortgaged
    if asset_state.is_mortgaged:
        raise HTTPException(status_code=400, detail="Property is already mortgaged")

    # Check if property has improvements
    if asset_state.improvement_level > 0 or asset_state.has_hotel:
        raise HTTPException(
            status_code=400,
            detail="Cannot mortgage property with improvements. Sell all houses and hotels first."
        )

    # If property is part of a monopoly, check that no other properties in the group have improvements
    if asset.asset_type == 'property':
        group_assets = get_property_group(session, asset_id)
        group_asset_ids = [a["asset_id"] for a in group_assets]

        # Check if any property in group has improvements
        any_improvements = session.query(models.AssetState).filter(
            models.AssetState.game_id == game_id,
            models.AssetState.asset_id.in_(group_asset_ids),
            (models.AssetState.improvement_level > 0) | (models.AssetState.has_hotel == True)
        ).first()

        if any_improvements:
            raise HTTPException(
                status_code=400,
                detail="Cannot mortgage while any property in color group has improvements"
            )

    # Mortgage the property
    asset_state.is_mortgaged = True
    mortgage_value = asset.mortgage_value

    # Get current turn
    current_turn = session.query(models.Turn).filter_by(
        game_id=game_id
    ).order_by(models.Turn.turn_id.desc()).first()
    turn_id = current_turn.turn_id if current_turn else None

    # Give player mortgage value
    ledger = LedgerService(session, game_id)
    ledger.receive_from_bank(
        player=player,
        amount=mortgage_value,
        txn_type="mortgage",
        turn_id=turn_id,
        asset_id=asset_id,
        notes=f"Mortgaged property"
    )

    session.commit()

    return {
        "status": "success",
        "is_mortgaged": True,
        "mortgage_value": mortgage_value
    }


@router.post("/properties/{asset_id}/unmortgage")
async def unmortgage_property(
    game_id: int,
    asset_id: int,
    auth_data: tuple[int, int] = Depends(auth.verify_session_token),
    session: Session = Depends(deps.get_session)
):
    """Unmortgage a property by paying mortgage value plus 10% interest"""
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

    # Check if property is mortgaged
    if not asset_state.is_mortgaged:
        raise HTTPException(status_code=400, detail="Property is not mortgaged")

    # Calculate unmortgage cost (mortgage value + 10%)
    mortgage_value = asset.mortgage_value
    unmortgage_cost = int(mortgage_value * 1.10)

    # Check player has sufficient funds
    ledger = LedgerService(session, game_id)
    balance = ledger.player_balance(player.game_player_id)

    if balance < unmortgage_cost:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient funds. Need ${unmortgage_cost}, have ${balance}"
        )

    # Unmortgage the property
    asset_state.is_mortgaged = False

    # Get current turn
    current_turn = session.query(models.Turn).filter_by(
        game_id=game_id
    ).order_by(models.Turn.turn_id.desc()).first()
    turn_id = current_turn.turn_id if current_turn else None

    # Charge player unmortgage cost
    ledger.pay_bank(
        player=player,
        amount=unmortgage_cost,
        txn_type="unmortgage",
        turn_id=turn_id,
        asset_id=asset_id,
        notes=f"Unmortgaged property (mortgage + 10% interest)"
    )

    session.commit()

    return {
        "status": "success",
        "is_mortgaged": False,
        "cost": unmortgage_cost
    }
