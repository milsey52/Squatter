"""add logged_in column to game_players

Revision ID: c3d4e5f6g7h8
Revises: ab54169d65cf
Create Date: 2026-02-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6g7h8'
down_revision: Union[str, Sequence[str], None] = 'ab54169d65cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add logged_in column to game_players table.

    This column tracks whether a player is currently logged into the game.
    Defaults to True for existing players.
    """
    op.add_column(
        "game_players",
        sa.Column("logged_in", sa.Boolean(), nullable=False, server_default=sa.text("true"))
    )


def downgrade() -> None:
    """Remove logged_in column from game_players table."""
    op.drop_column("game_players", "logged_in")
