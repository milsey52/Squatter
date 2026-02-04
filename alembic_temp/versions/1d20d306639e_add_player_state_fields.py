"""add player state fields

Revision ID: 1d20d306639e
Revises: 28166870d578
Create Date: 2026-01-18 14:00:08.809427

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1d20d306639e'
down_revision: Union[str, Sequence[str], None] = '28166870d578'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("game_players", sa.Column("current_space_id", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("game_players", sa.Column("in_jail", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("game_players", sa.Column("jail_turns", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("game_players", sa.Column("double_streak", sa.Integer(), nullable=False, server_default="0"))
    # Note: SQLite doesn't support ALTER COLUMN to drop server defaults
    # Server defaults will remain in the schema (harmless for SQLite)


def downgrade():
    op.drop_column("game_players", "double_streak")
    op.drop_column("game_players", "jail_turns")
    op.drop_column("game_players", "in_jail")
    op.drop_column("game_players", "current_space_id")
