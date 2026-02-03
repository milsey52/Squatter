"""fix_current_space_id_default_to_zero

Revision ID: ab54169d65cf
Revises: 0ed98078e5cf
Create Date: 2026-02-03 13:14:14.578378

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ab54169d65cf'
down_revision: Union[str, Sequence[str], None] = '0ed98078e5cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Fix current_space_id for players at position 1.

    The game uses 0-based indexing (0-39) where position 0 is Start/Payday.
    However, the database default was '1', causing new players in lobbies
    to start at position 1 (Belvue House) instead of position 0.

    This migration updates any players still at position 1 to position 0,
    assuming they haven't moved yet (games in lobby status).
    """
    # Update players at position 1 to position 0
    # Only update players in games that are still in lobby (haven't started)
    op.execute("""
        UPDATE game_players
        SET current_space_id = 0
        WHERE current_space_id = 1
        AND game_id IN (SELECT game_id FROM games WHERE status = 'lobby')
    """)


def downgrade() -> None:
    """Revert current_space_id changes."""
    # Revert position 0 back to 1 for games in lobby
    op.execute("""
        UPDATE game_players
        SET current_space_id = 1
        WHERE current_space_id = 0
        AND game_id IN (SELECT game_id FROM games WHERE status = 'lobby')
    """)
