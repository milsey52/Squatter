from sqlalchemy.orm import Session
from app import models

def seed_asset_states(session: Session, game_id: int):
    assets = session.query(models.Asset).all()
    for asset in assets:
        session.add(models.AssetState(
            game_id=game_id,
            asset_id=asset.asset_id,
            owner_game_player_id=None,
            is_mortgaged=False,
            improvement_level=0,
            has_hotel=False,
        ))

def create_game_with_defaults(session: Session, host_user_id: int, player_names: list[str]):
    # 1. Create the game
    game = models.Game(host_user_id=host_user_id, status="in_progress")
    session.add(game)
    session.flush()   # assigns game.game_id

    # 2. Add each player
    for order, name in enumerate(player_names, start=1):
        session.add(models.GamePlayer(
            game_id=game.game_id,
            player_name=name,
            turn_order=order,
            current_space_id=0,  # Start/Payday
            in_jail=False,
            jail_turns=0,
            double_streak=0,
        ))

    # 3. Seed asset states
    seed_asset_states(session, game.game_id)

    # 4. Create house rules (or use defaults)
    session.add(models.HouseRule(
        game_id=game.game_id,
        starting_cash=2000,
        pass_start_bonus=2000,
        jackpot_enabled=True,
    ))

    # 5. Commit everything
    session.commit()

    return game.game_id