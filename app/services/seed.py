# app/services/seed.py
from app import models

def seed_asset_states(session, game_id: int):
    assets = session.query(models.Asset).all()
    for asset in assets:
        session.add(
            models.AssetState(
                game_id=game_id,
                asset_id=asset.asset_id,
                owner_game_player_id=None,
                is_mortgaged=False,
                improvement_level=0,
                has_hotel=False,
            )
        )
    session.flush()