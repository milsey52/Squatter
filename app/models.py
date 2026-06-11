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
    sessions = relationship("GameSession", back_populates="user")


class GameSession(Base):
    __tablename__ = "game_sessions"
    session_token = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="sessions")
    game = relationship("Game")


class Game(Base):
    __tablename__ = "games"
    game_id = Column(Integer, primary_key=True)
    host_user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    game_code = Column(String(6), unique=True, nullable=False, index=True)
    status = Column(String, nullable=False, default="lobby")
    max_players = Column(Integer, nullable=False, default=6)
    current_game_player_id = Column(Integer, ForeignKey("game_players.game_player_id"))
    created_at = Column(DateTime, server_default=func.now())
    last_saved_at = Column(DateTime)
    current_turn_order_round = Column(Integer, nullable=False, default=1)

    host = relationship("User", back_populates="games_hosted")
    game_rules = relationship("GameRule", back_populates="game", uselist=False)
    players = relationship("GamePlayer", back_populates="game", foreign_keys="[GamePlayer.game_id]")
    turns = relationship("Turn", back_populates="game")
    current_player = relationship("GamePlayer", foreign_keys=[current_game_player_id])


class GameRule(Base):
    __tablename__ = "game_rules"
    game_id = Column(Integer, ForeignKey("games.game_id"), primary_key=True)
    starting_cash = Column(Integer, nullable=False, default=2000)
    quick_game = Column(Boolean, nullable=False, default=False)
    starting_paddock_type = Column(String, nullable=False, default="natural")
    allow_trading = Column(Boolean, nullable=False, default=True)
    notes = Column(Text)
    # How long an AI-owned modal sits on humans' screens before the AI
    # dismisses it. 1-10s; host adjustable via the Settings modal.
    ai_reaction_time_seconds = Column(Integer, nullable=False, default=4)

    game = relationship("Game", back_populates="game_rules")


class GamePlayer(Base):
    __tablename__ = "game_players"
    game_player_id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id"))
    player_name = Column(String, nullable=False)
    turn_order = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)
    is_ready = Column(Boolean, nullable=False, default=False)
    logged_in = Column(Boolean, nullable=False, default=True)
    # Per-player rejoin credential, issued at join time. Required to rejoin
    # under this player's name from a device without the session token.
    # NULL for AI players and legacy rows (which then cannot name-rejoin).
    rejoin_code = Column(String, nullable=True)
    current_board_index = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now())

    # Squatter-specific fields
    visiting_town_turns = Column(Integer, nullable=False, default=0)
    is_in_drought = Column(Boolean, nullable=False, default=False)
    drought_start_space = Column(Integer)
    drought_spaces_remaining = Column(Integer, nullable=False, default=0)
    has_haystack = Column(Boolean, nullable=False, default=False)
    haystack_used = Column(Boolean, nullable=False, default=False)
    bore_dried_up = Column(Boolean, nullable=False, default=False)
    restock_blocked_until_circuit = Column(Boolean, nullable=False, default=False)
    restock_block_spaces_remaining = Column(Integer, nullable=False, default=0)
    # 'all' (Lucerne Flea / Grass Fire) or 'irrigated' (Bore Dries Up); NULL when no block.
    restock_block_scope = Column(String, nullable=True)
    # Worm Infestation rule: clear the restock block on landing at any
    # Stock Sale space (not after a full circuit).
    restock_block_until_stock_sale = Column(Boolean, nullable=False, default=False)
    # Where the restock block began — used to draw the circuit marker on
    # the board. NULL when no block is active.
    restock_block_marker_board_index = Column(Integer, nullable=True)
    # Which card triggered the block — 'lucerne_flea', 'grass_fire', or
    # 'worm_infestation'. Drives the marker shape. NULL when no block.
    restock_block_source = Column(String, nullable=True)

    # AI player flags. is_ai=True players have user_id=NULL and no session;
    # the server-side autopilot drives their turns.
    is_ai = Column(Boolean, nullable=False, default=False)
    ai_difficulty = Column(String, nullable=True)  # 'easy' | 'medium' | 'hard'
    wool_cheque_bonus = Column(Integer, nullable=False, default=0)
    next_sell_price_modifier = Column(Integer, nullable=False, default=0)
    footrot_immune = Column(Boolean, nullable=False, default=False)
    next_drought_halved = Column(Boolean, nullable=False, default=False)
    wool_cheque_blowfly_pct = Column(Integer, nullable=False, default=0)

    game = relationship("Game", back_populates="players", foreign_keys=[game_id])
    user = relationship("User", back_populates="players")
    paddocks = relationship("Paddock", back_populates="owner")

    __table_args__ = (
        UniqueConstraint("game_id", "turn_order", name="uq_game_player_turn"),
    )


class Space(Base):
    __tablename__ = "spaces"
    space_id = Column(Integer, primary_key=True)
    board_index = Column(Integer, unique=True, nullable=False)
    name = Column(String, nullable=False)
    space_type = Column(String, nullable=False)
    season = Column(String)  # NULL or "Haymaking"

    # Cost fields for expense spaces
    cost_per_pen = Column(Integer)
    cost_flat = Column(Integer)
    cost_per_pen_with_card = Column(Integer)
    cost_flat_with_card = Column(Integer)
    relevant_card_name = Column(String)

    # Stud ram fields
    purchase_price = Column(Integer)
    sell_back_price = Column(Integer)
    stud_fee = Column(Integer)


class Paddock(Base):
    __tablename__ = "paddocks"
    paddock_id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False)
    owner_game_player_id = Column(Integer, ForeignKey("game_players.game_player_id"), nullable=False)
    paddock_number = Column(Integer, nullable=False)
    paddock_type = Column(String, nullable=False, default="natural")
    sheep_pens = Column(Integer, nullable=False, default=3)
    max_pens = Column(Integer, nullable=False, default=3)
    is_mortgaged = Column(Boolean, nullable=False, default=False)

    owner = relationship("GamePlayer", back_populates="paddocks")

    __table_args__ = (
        UniqueConstraint("game_id", "owner_game_player_id", "paddock_number",
                         name="uq_paddock"),
    )


class StudRamState(Base):
    __tablename__ = "stud_ram_states"
    stud_ram_state_id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False)
    space_id = Column(Integer, ForeignKey("spaces.space_id"), nullable=False)
    owner_game_player_id = Column(Integer, ForeignKey("game_players.game_player_id"))
    is_available = Column(Boolean, nullable=False, default=True)

    space = relationship("Space")
    owner = relationship("GamePlayer")

    __table_args__ = (
        UniqueConstraint("game_id", "space_id", name="uq_stud_ram_game_space"),
    )


class StockCard(Base):
    __tablename__ = "stock_cards"
    stock_card_id = Column(Integer, primary_key=True)
    buy_price_per_pen = Column(Integer, nullable=False)
    sell_price_natural = Column(Integer, nullable=False)
    sell_price_improved_irrigated = Column(Integer, nullable=False)


class StockCardDraw(Base):
    __tablename__ = "stock_card_draws"
    stock_card_draw_id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False)
    turn_id = Column(Integer, ForeignKey("turns.turn_id"), nullable=False)
    stock_card_id = Column(Integer, ForeignKey("stock_cards.stock_card_id"), nullable=False)
    draw_order = Column(Integer, nullable=False)

    stock_card = relationship("StockCard")
    turn = relationship("Turn")


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
    space_id = Column(Integer, ForeignKey("spaces.space_id"))
    card_id = Column(Integer, ForeignKey("cards.card_id"))
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())


class Card(Base):
    __tablename__ = "cards"
    card_id = Column(Integer, primary_key=True)
    deck_type = Column(String, nullable=False)  # "tucker_bag"
    title = Column(String, nullable=False)
    body_text = Column(Text, nullable=False)
    is_retainable = Column(Boolean, default=False, nullable=False)
    one_time = Column(Boolean, default=False, nullable=False)  # drawn at most once per game
    effect_code = Column(String, nullable=False)
    effect_params = Column(Text)  # JSON


class CardDraw(Base):
    __tablename__ = "card_draws"
    card_draw_id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False)
    turn_id = Column(Integer, ForeignKey("turns.turn_id"), nullable=False)
    deck_type = Column(String, nullable=False)
    card_id = Column(Integer, ForeignKey("cards.card_id"), nullable=False)
    draw_order = Column(Integer, nullable=False)
    kept_by_player_id = Column(Integer, ForeignKey("game_players.game_player_id"))
    resolved_at = Column(DateTime)
    discarded_at = Column(DateTime)
    notes = Column(Text)

    card = relationship("Card")
    turn = relationship("Turn")
    kept_by_player = relationship("GamePlayer")


class PendingAction(Base):
    __tablename__ = "pending_actions"
    pending_action_id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False)
    turn_id = Column(Integer, ForeignKey("turns.turn_id"), nullable=False)
    action_type = Column(String(50), nullable=False)
    active_player_id = Column(Integer, ForeignKey("game_players.game_player_id"))
    action_data = Column(Text)  # JSON
    created_at = Column(DateTime, server_default=func.now())
    resolved_at = Column(DateTime)

    game = relationship("Game")
    turn = relationship("Turn")
    active_player = relationship("GamePlayer")


class TradeSession(Base):
    __tablename__ = "trade_sessions"
    trade_session_id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False)
    initiator_player_id = Column(Integer, ForeignKey("game_players.game_player_id"), nullable=False)
    counterparty_player_id = Column(Integer, ForeignKey("game_players.game_player_id"))
    status = Column(String(50), nullable=False, default="pending_invite")
    initiator_offer = Column(Text)  # JSON: {cash: int, stud_ram_ids: []}
    counterparty_offer = Column(Text)  # JSON
    initiator_accepted = Column(Boolean, nullable=False, default=False)
    counterparty_accepted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    completed_at = Column(DateTime)

    game = relationship("Game")
    initiator = relationship("GamePlayer", foreign_keys=[initiator_player_id])
    counterparty = relationship("GamePlayer", foreign_keys=[counterparty_player_id])


class TurnOrderRoll(Base):
    __tablename__ = "turn_order_rolls"
    roll_id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False)
    game_player_id = Column(Integer, ForeignKey("game_players.game_player_id"), nullable=False)
    round_number = Column(Integer, nullable=False, default=1)
    dice_roll_1 = Column(Integer, nullable=False)
    dice_roll_2 = Column(Integer, nullable=False)
    total = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    game = relationship("Game")
    player = relationship("GamePlayer")

    __table_args__ = (
        UniqueConstraint("game_id", "game_player_id", "round_number",
                         name="uq_turn_order_roll"),
    )
