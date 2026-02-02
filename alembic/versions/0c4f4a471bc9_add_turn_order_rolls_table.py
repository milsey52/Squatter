"""add_turn_order_rolls_table

Revision ID: 0c4f4a471bc9
Revises: 790fe9c0f650
Create Date: 2026-02-02 18:49:58.837934

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0c4f4a471bc9'
down_revision: Union[str, Sequence[str], None] = '790fe9c0f650'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'turn_order_rolls',
        sa.Column('roll_id', sa.Integer(), nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('game_player_id', sa.Integer(), nullable=False),
        sa.Column('round_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('dice_roll_1', sa.Integer(), nullable=False),
        sa.Column('dice_roll_2', sa.Integer(), nullable=False),
        sa.Column('total', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['game_id'], ['games.game_id']),
        sa.ForeignKeyConstraint(['game_player_id'], ['game_players.game_player_id']),
        sa.PrimaryKeyConstraint('roll_id'),
        sa.UniqueConstraint('game_id', 'game_player_id', 'round_number', name='uq_turn_order_roll')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('turn_order_rolls')
