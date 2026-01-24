from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db import Base

class User(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True)
    display_name = Column(String, nullable=False)
    email = Column(String, unique=True)
    created_at = Column(DateTime, server_default=func.now())

    games_hosted = relationship("Game", back_populates="host")
    players = relationship("GamePlayer", back_populates="user")

class Game(Base):
    __tablename__ = "games"
    game_id = Column(Integer, primary_key=True)
    host_user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    status = Column(String, nullable=False, default="in_progress")
    current_game_player_id = Column(Integer, ForeignKey("game_players.game_player_id"))
    created_at = Column(DateTime, server_default=func.now())
    last_saved_at = Column(DateTime)

    host = relationship("User", back_populates="games_hosted")
    house_rules = relationship("HouseRule", back_populates="game", uselist=False)
    players = relationship("GamePlayer", back_populates="game", foreign_keys="[GamePlayer.game_id]")
    turns = relationship("Turn", back_populates="game")
    current_player = relationship("GamePlayer", foreign_keys=[current_game_player_id])

class HouseRule(Base):
    __tablename__ = "house_rules"
    game_id = Column(Integer, ForeignKey("games.game_id"), primary_key=True)
    starting_cash = Column(Integer, nullable=False)
    pass_start_bonus = Column(Integer, nullable=False)
    jackpot_enabled = Column(Boolean, default=True)
    allow_auctions = Column(Boolean, default=True)
    allow_trading = Column(Boolean, default=True)
    notes = Column(Text)

    game = relationship("Game", back_populates="house_rules")

class GamePlayer(Base):
    __tablename__ = "game_players"
    game_player_id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id"))
    player_name = Column(String, nullable=False)
    turn_order = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)
    current_space_id = Column(Integer, nullable=False, default=1)
    in_jail = Column(Boolean, nullable=False, default=False)
    jail_turns = Column(Integer, nullable=False, default=0)
    double_streak = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now())

    game = relationship("Game", back_populates="players", foreign_keys=[game_id])
    user = relationship("User", back_populates="players")

    __table_args__ = (
        UniqueConstraint("game_id", "turn_order", name="uq_game_player_turn"),
    )

class PropertyGroup(Base):
    __tablename__ = "property_groups"
    group_id = Column(Integer, primary_key=True)
    group_name = Column(String, nullable=False)
    color_hex = Column(String, nullable=False)
    house_cost = Column(Integer, nullable=False)
    hotel_cost = Column(Integer, nullable=False)

class Space(Base):
    __tablename__ = "spaces"
    space_id = Column(Integer, primary_key=True)
    board_index = Column(Integer, unique=True, nullable=False)
    name = Column(String, nullable=False)
    space_type = Column(String, nullable=False)
    group_id = Column(Integer, ForeignKey("property_groups.group_id"))
    asset_id = Column(Integer)  # filled after assets created

class Asset(Base):
    __tablename__ = "assets"
    asset_id = Column(Integer, primary_key=True)
    space_id = Column(Integer, ForeignKey("spaces.space_id"), unique=True, nullable=False)
    asset_type = Column(String, nullable=False)
    purchase_price = Column(Integer, nullable=False)
    mortgage_value = Column(Integer, nullable=False)
    rent_base = Column(Integer)
    rent_group = Column(Integer)
    rent_house_1 = Column(Integer)
    rent_house_2 = Column(Integer)
    rent_house_3 = Column(Integer)
    rent_house_4 = Column(Integer)
    rent_hotel = Column(Integer)
    rent_tier_2 = Column(Integer)
    rent_tier_3 = Column(Integer)
    rent_tier_4 = Column(Integer)
    utility_mult_single = Column(Integer)
    utility_mult_double = Column(Integer)

class AssetState(Base):
    __tablename__ = "asset_states"
    asset_state_id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.asset_id"), nullable=False)
    owner_game_player_id = Column(Integer, ForeignKey("game_players.game_player_id"))
    is_mortgaged = Column(Boolean, default=False)
    improvement_level = Column(Integer, default=0)
    has_hotel = Column(Boolean, default=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("game_id", "asset_id", name="uq_asset_state_game_asset"),
    )

class Turn(Base):
    __tablename__ = "turns"

    turn_id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False)
    turn_number = Column(Integer, nullable=False)
    active_game_player_id = Column(Integer, ForeignKey("game_players.game_player_id"), nullable=False)
    dice_roll_1 = Column(Integer)
    dice_roll_2 = Column(Integer)
    is_double = Column(Boolean, default=False)
    double_count = Column(Integer, default=0)
    started_at = Column(DateTime, server_default=func.now())
    game = relationship("Game", back_populates="turns")
    active_player = relationship("GamePlayer")
    movements = relationship("Movement", back_populates="turn")

class Movement(Base):
    __tablename__ = "movements"

    movement_id = Column(Integer, primary_key=True, autoincrement=True)
    turn_id = Column(Integer, ForeignKey("turns.turn_id"), nullable=False)
    game_player_id = Column(Integer, ForeignKey("game_players.game_player_id"), nullable=False)
    start_space_id = Column(Integer, ForeignKey("spaces.space_id"), nullable=False)
    end_space_id = Column(Integer, ForeignKey("spaces.space_id"), nullable=False)
    movement_type = Column(String, nullable=False)
    distance = Column(Integer)
    passed_start = Column(Boolean, default=False)
    notes = Column(Text)

    turn = relationship("Turn", back_populates="movements")
    player = relationship("GamePlayer")
    start_space = relationship("Space", foreign_keys=[start_space_id])
    end_space = relationship("Space", foreign_keys=[end_space_id])

class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False)
    turn_id = Column(Integer, ForeignKey("turns.turn_id"))
    sequence_in_turn = Column(Integer)
    player_from_id = Column(Integer, ForeignKey("game_players.game_player_id"))
    player_to_id = Column(Integer, ForeignKey("game_players.game_player_id"))
    amount = Column(Integer, nullable=False)
    transaction_type = Column(String, nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.asset_id"))
    space_id = Column(Integer, ForeignKey("spaces.space_id"))
    card_id = Column(Integer, ForeignKey("cards.card_id"))
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

class Card(Base):
    __tablename__ = "cards"
    card_id = Column(Integer, primary_key=True)
    deck_type = Column(String, nullable=False)      # <-- ensure this line exists
    title = Column(String, nullable=False)
    body_text = Column(Text, nullable=False)
    is_retainable = Column(Boolean, default=False, nullable=False)
    effect_code = Column(String, nullable=False)
    effect_params = Column(Text)

class CardDraw(Base):
    __tablename__ = "card_draws"

    card_draw_id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False)
    turn_id = Column(Integer, ForeignKey("turns.turn_id"), nullable=False)
    deck_type = Column(String, nullable=False)  # or Enum if you prefer
    card_id = Column(Integer, ForeignKey("cards.card_id"), nullable=False)
    draw_order = Column(Integer, nullable=False)
    kept_by_player_id = Column(Integer, ForeignKey("game_players.game_player_id"))
    resolved_at = Column(DateTime)
    discarded_at = Column(DateTime)
    notes = Column(Text)

    card = relationship("Card")
    turn = relationship("Turn")
    kept_by_player = relationship("GamePlayer")

class JackpotLedger(Base):
    __tablename__ = "jackpot_ledger"

    jackpot_entry_id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False)
    turn_id = Column(Integer, ForeignKey("turns.turn_id"))
    transaction_id = Column(Integer, ForeignKey("transactions.transaction_id"))
    delta_amount = Column(Integer, nullable=False)
    balance_after = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    game = relationship("Game")
    turn = relationship("Turn")
    transaction = relationship("Transaction")