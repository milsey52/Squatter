"""squatter_schema

Revision ID: 5745db216216
Revises:
Create Date: 2026-05-01 21:40:05.619076

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5745db216216'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Independent tables first
    op.create_table('users',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('display_name', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('user_id'),
        sa.UniqueConstraint('email')
    )

    op.create_table('cards',
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('deck_type', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('body_text', sa.Text(), nullable=False),
        sa.Column('is_retainable', sa.Boolean(), nullable=False),
        sa.Column('effect_code', sa.String(), nullable=False),
        sa.Column('effect_params', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('card_id')
    )

    op.create_table('spaces',
        sa.Column('space_id', sa.Integer(), nullable=False),
        sa.Column('board_index', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('space_type', sa.String(), nullable=False),
        sa.Column('season', sa.String(), nullable=True),
        sa.Column('cost_per_pen', sa.Integer(), nullable=True),
        sa.Column('cost_flat', sa.Integer(), nullable=True),
        sa.Column('cost_per_pen_with_card', sa.Integer(), nullable=True),
        sa.Column('cost_flat_with_card', sa.Integer(), nullable=True),
        sa.Column('relevant_card_name', sa.String(), nullable=True),
        sa.Column('purchase_price', sa.Integer(), nullable=True),
        sa.Column('sell_back_price', sa.Integer(), nullable=True),
        sa.Column('stud_fee', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('space_id'),
        sa.UniqueConstraint('board_index')
    )

    op.create_table('stock_cards',
        sa.Column('stock_card_id', sa.Integer(), nullable=False),
        sa.Column('buy_price_per_pen', sa.Integer(), nullable=False),
        sa.Column('sell_price_natural', sa.Integer(), nullable=False),
        sa.Column('sell_price_improved_irrigated', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('stock_card_id')
    )

    # Games table WITHOUT the circular FK (added later)
    op.create_table('games',
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('host_user_id', sa.Integer(), nullable=False),
        sa.Column('game_code', sa.String(length=6), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('max_players', sa.Integer(), nullable=False),
        sa.Column('current_game_player_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('last_saved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['host_user_id'], ['users.user_id']),
        sa.PrimaryKeyConstraint('game_id')
    )
    op.create_index(op.f('ix_games_game_code'), 'games', ['game_code'], unique=True)

    # Game players (references games)
    op.create_table('game_players',
        sa.Column('game_player_id', sa.Integer(), nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('player_name', sa.String(), nullable=False),
        sa.Column('turn_order', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('is_ready', sa.Boolean(), nullable=False),
        sa.Column('logged_in', sa.Boolean(), nullable=False),
        sa.Column('current_space_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('visiting_town_turns', sa.Integer(), nullable=False),
        sa.Column('is_in_drought', sa.Boolean(), nullable=False),
        sa.Column('drought_start_space', sa.Integer(), nullable=True),
        sa.Column('drought_spaces_remaining', sa.Integer(), nullable=False),
        sa.Column('has_haystack', sa.Boolean(), nullable=False),
        sa.Column('haystack_used', sa.Boolean(), nullable=False),
        sa.Column('bore_dried_up', sa.Boolean(), nullable=False),
        sa.Column('restock_blocked_until_circuit', sa.Boolean(), nullable=False),
        sa.Column('wool_cheque_bonus', sa.Integer(), nullable=False),
        sa.Column('next_sell_price_modifier', sa.Integer(), nullable=False),
        sa.Column('footrot_immune', sa.Boolean(), nullable=False),
        sa.Column('next_drought_halved', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['game_id'], ['games.game_id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id']),
        sa.PrimaryKeyConstraint('game_player_id'),
        sa.UniqueConstraint('game_id', 'turn_order', name='uq_game_player_turn')
    )

    # Now add the circular FK from games -> game_players
    op.create_foreign_key(
        'fk_games_current_player', 'games', 'game_players',
        ['current_game_player_id'], ['game_player_id']
    )

    # Tables that depend on games and/or game_players
    op.create_table('game_rules',
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('starting_cash', sa.Integer(), nullable=False),
        sa.Column('quick_game', sa.Boolean(), nullable=False),
        sa.Column('starting_paddock_type', sa.String(), nullable=False),
        sa.Column('allow_trading', sa.Boolean(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['game_id'], ['games.game_id']),
        sa.PrimaryKeyConstraint('game_id')
    )

    op.create_table('game_sessions',
        sa.Column('session_token', sa.String(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['game_id'], ['games.game_id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id']),
        sa.PrimaryKeyConstraint('session_token')
    )

    op.create_table('paddocks',
        sa.Column('paddock_id', sa.Integer(), nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('owner_game_player_id', sa.Integer(), nullable=False),
        sa.Column('paddock_number', sa.Integer(), nullable=False),
        sa.Column('paddock_type', sa.String(), nullable=False),
        sa.Column('sheep_pens', sa.Integer(), nullable=False),
        sa.Column('max_pens', sa.Integer(), nullable=False),
        sa.Column('is_mortgaged', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['game_id'], ['games.game_id']),
        sa.ForeignKeyConstraint(['owner_game_player_id'], ['game_players.game_player_id']),
        sa.PrimaryKeyConstraint('paddock_id'),
        sa.UniqueConstraint('game_id', 'owner_game_player_id', 'paddock_number', name='uq_paddock')
    )

    op.create_table('stud_ram_states',
        sa.Column('stud_ram_state_id', sa.Integer(), nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('space_id', sa.Integer(), nullable=False),
        sa.Column('owner_game_player_id', sa.Integer(), nullable=True),
        sa.Column('is_available', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['game_id'], ['games.game_id']),
        sa.ForeignKeyConstraint(['owner_game_player_id'], ['game_players.game_player_id']),
        sa.ForeignKeyConstraint(['space_id'], ['spaces.space_id']),
        sa.PrimaryKeyConstraint('stud_ram_state_id'),
        sa.UniqueConstraint('game_id', 'space_id', name='uq_stud_ram_game_space')
    )

    op.create_table('trade_sessions',
        sa.Column('trade_session_id', sa.Integer(), nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('initiator_player_id', sa.Integer(), nullable=False),
        sa.Column('counterparty_player_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('initiator_offer', sa.Text(), nullable=True),
        sa.Column('counterparty_offer', sa.Text(), nullable=True),
        sa.Column('initiator_accepted', sa.Boolean(), nullable=False),
        sa.Column('counterparty_accepted', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['counterparty_player_id'], ['game_players.game_player_id']),
        sa.ForeignKeyConstraint(['game_id'], ['games.game_id']),
        sa.ForeignKeyConstraint(['initiator_player_id'], ['game_players.game_player_id']),
        sa.PrimaryKeyConstraint('trade_session_id')
    )

    op.create_table('turn_order_rolls',
        sa.Column('roll_id', sa.Integer(), nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('game_player_id', sa.Integer(), nullable=False),
        sa.Column('round_number', sa.Integer(), nullable=False),
        sa.Column('dice_roll_1', sa.Integer(), nullable=False),
        sa.Column('dice_roll_2', sa.Integer(), nullable=False),
        sa.Column('total', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['game_id'], ['games.game_id']),
        sa.ForeignKeyConstraint(['game_player_id'], ['game_players.game_player_id']),
        sa.PrimaryKeyConstraint('roll_id'),
        sa.UniqueConstraint('game_id', 'game_player_id', 'round_number', name='uq_turn_order_roll')
    )

    op.create_table('turns',
        sa.Column('turn_id', sa.Integer(), nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('turn_number', sa.Integer(), nullable=False),
        sa.Column('active_game_player_id', sa.Integer(), nullable=False),
        sa.Column('dice_roll_1', sa.Integer(), nullable=True),
        sa.Column('dice_roll_2', sa.Integer(), nullable=True),
        sa.Column('is_double', sa.Boolean(), nullable=True),
        sa.Column('double_count', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['active_game_player_id'], ['game_players.game_player_id']),
        sa.ForeignKeyConstraint(['game_id'], ['games.game_id']),
        sa.PrimaryKeyConstraint('turn_id')
    )

    # Tables that depend on turns
    op.create_table('card_draws',
        sa.Column('card_draw_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('turn_id', sa.Integer(), nullable=False),
        sa.Column('deck_type', sa.String(), nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('draw_order', sa.Integer(), nullable=False),
        sa.Column('kept_by_player_id', sa.Integer(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('discarded_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['card_id'], ['cards.card_id']),
        sa.ForeignKeyConstraint(['game_id'], ['games.game_id']),
        sa.ForeignKeyConstraint(['kept_by_player_id'], ['game_players.game_player_id']),
        sa.ForeignKeyConstraint(['turn_id'], ['turns.turn_id']),
        sa.PrimaryKeyConstraint('card_draw_id')
    )

    op.create_table('movements',
        sa.Column('movement_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('turn_id', sa.Integer(), nullable=False),
        sa.Column('game_player_id', sa.Integer(), nullable=False),
        sa.Column('start_space_id', sa.Integer(), nullable=False),
        sa.Column('end_space_id', sa.Integer(), nullable=False),
        sa.Column('movement_type', sa.String(), nullable=False),
        sa.Column('distance', sa.Integer(), nullable=True),
        sa.Column('passed_start', sa.Boolean(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['end_space_id'], ['spaces.space_id']),
        sa.ForeignKeyConstraint(['game_player_id'], ['game_players.game_player_id']),
        sa.ForeignKeyConstraint(['start_space_id'], ['spaces.space_id']),
        sa.ForeignKeyConstraint(['turn_id'], ['turns.turn_id']),
        sa.PrimaryKeyConstraint('movement_id')
    )

    op.create_table('pending_actions',
        sa.Column('pending_action_id', sa.Integer(), nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('turn_id', sa.Integer(), nullable=False),
        sa.Column('action_type', sa.String(length=50), nullable=False),
        sa.Column('active_player_id', sa.Integer(), nullable=True),
        sa.Column('action_data', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['active_player_id'], ['game_players.game_player_id']),
        sa.ForeignKeyConstraint(['game_id'], ['games.game_id']),
        sa.ForeignKeyConstraint(['turn_id'], ['turns.turn_id']),
        sa.PrimaryKeyConstraint('pending_action_id')
    )

    op.create_table('stock_card_draws',
        sa.Column('stock_card_draw_id', sa.Integer(), nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('turn_id', sa.Integer(), nullable=False),
        sa.Column('stock_card_id', sa.Integer(), nullable=False),
        sa.Column('draw_order', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['game_id'], ['games.game_id']),
        sa.ForeignKeyConstraint(['stock_card_id'], ['stock_cards.stock_card_id']),
        sa.ForeignKeyConstraint(['turn_id'], ['turns.turn_id']),
        sa.PrimaryKeyConstraint('stock_card_draw_id')
    )

    op.create_table('transactions',
        sa.Column('transaction_id', sa.Integer(), nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('turn_id', sa.Integer(), nullable=True),
        sa.Column('sequence_in_turn', sa.Integer(), nullable=True),
        sa.Column('player_from_id', sa.Integer(), nullable=True),
        sa.Column('player_to_id', sa.Integer(), nullable=True),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('transaction_type', sa.String(), nullable=False),
        sa.Column('space_id', sa.Integer(), nullable=True),
        sa.Column('card_id', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['card_id'], ['cards.card_id']),
        sa.ForeignKeyConstraint(['game_id'], ['games.game_id']),
        sa.ForeignKeyConstraint(['player_from_id'], ['game_players.game_player_id']),
        sa.ForeignKeyConstraint(['player_to_id'], ['game_players.game_player_id']),
        sa.ForeignKeyConstraint(['space_id'], ['spaces.space_id']),
        sa.ForeignKeyConstraint(['turn_id'], ['turns.turn_id']),
        sa.PrimaryKeyConstraint('transaction_id')
    )


def downgrade() -> None:
    op.drop_table('transactions')
    op.drop_table('stock_card_draws')
    op.drop_table('pending_actions')
    op.drop_table('movements')
    op.drop_table('card_draws')
    op.drop_table('turns')
    op.drop_table('turn_order_rolls')
    op.drop_table('trade_sessions')
    op.drop_table('stud_ram_states')
    op.drop_table('paddocks')
    op.drop_table('game_sessions')
    op.drop_table('game_rules')
    op.drop_constraint('fk_games_current_player', 'games', type_='foreignkey')
    op.drop_table('game_players')
    op.drop_index(op.f('ix_games_game_code'), table_name='games')
    op.drop_table('games')
    op.drop_table('stock_cards')
    op.drop_table('spaces')
    op.drop_table('cards')
    op.drop_table('users')
