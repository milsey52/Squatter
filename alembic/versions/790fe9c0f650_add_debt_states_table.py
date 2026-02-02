"""add_debt_states_table

Revision ID: 790fe9c0f650
Revises: 1a8a330ed1ba
Create Date: 2026-02-02 16:06:50.191056

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '790fe9c0f650'
down_revision: Union[str, Sequence[str], None] = '1a8a330ed1ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'debt_states',
        sa.Column('debt_state_id', sa.Integer(), nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('debtor_player_id', sa.Integer(), nullable=False),
        sa.Column('creditor_player_id', sa.Integer(), nullable=True),
        sa.Column('debt_amount', sa.Integer(), nullable=False),
        sa.Column('debt_reason', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('asset_id', sa.Integer(), nullable=True),
        sa.Column('turn_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['game_id'], ['games.game_id']),
        sa.ForeignKeyConstraint(['debtor_player_id'], ['game_players.game_player_id']),
        sa.ForeignKeyConstraint(['creditor_player_id'], ['game_players.game_player_id']),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.asset_id']),
        sa.ForeignKeyConstraint(['turn_id'], ['turns.turn_id']),
        sa.PrimaryKeyConstraint('debt_state_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('debt_states')
