"""add trade acceptance fields

Revision ID: 1a8a330ed1ba
Revises: f5535833a837
Create Date: 2026-01-29 21:53:36.108859

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1a8a330ed1ba'
down_revision: Union[str, Sequence[str], None] = 'f5535833a837'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("trade_sessions", sa.Column("initiator_accepted", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("trade_sessions", sa.Column("counterparty_accepted", sa.Boolean(), nullable=False, server_default=sa.text("false")))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("trade_sessions", "counterparty_accepted")
    op.drop_column("trade_sessions", "initiator_accepted")
