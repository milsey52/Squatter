"""add_trade_acceptance_columns

Revision ID: 0ed98078e5cf
Revises: e275df77f298
Create Date: 2026-02-02 22:00:30.102756

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0ed98078e5cf'
down_revision: Union[str, Sequence[str], None] = 'e275df77f298'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add initiator_accepted and counterparty_accepted columns to trade_sessions."""
    op.add_column('trade_sessions', sa.Column('initiator_accepted', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('trade_sessions', sa.Column('counterparty_accepted', sa.Boolean(), nullable=False, server_default='0'))


def downgrade() -> None:
    """Remove acceptance columns."""
    op.drop_column('trade_sessions', 'counterparty_accepted')
    op.drop_column('trade_sessions', 'initiator_accepted')
