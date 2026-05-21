"""backfill columns missed by consolidated squatter_schema migration

Revision ID: a1b2c3d4e5f6
Revises: 5745db216216
Create Date: 2026-05-20 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '5745db216216'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'game_players',
        sa.Column(
            'restock_block_spaces_remaining',
            sa.Integer(),
            nullable=False,
            server_default='0',
        ),
    )
    op.add_column(
        'games',
        sa.Column(
            'current_turn_order_round',
            sa.Integer(),
            nullable=False,
            server_default='1',
        ),
    )
    op.add_column(
        'cards',
        sa.Column(
            'one_time',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
        ),
    )
    op.add_column(
        'game_players',
        sa.Column(
            'wool_cheque_blowfly_pct',
            sa.Integer(),
            nullable=False,
            server_default='0',
        ),
    )


def downgrade() -> None:
    op.drop_column('game_players', 'wool_cheque_blowfly_pct')
    op.drop_column('cards', 'one_time')
    op.drop_column('games', 'current_turn_order_round')
    op.drop_column('game_players', 'restock_block_spaces_remaining')
