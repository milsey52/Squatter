"""fix_board_index_to_zero_based

Revision ID: e275df77f298
Revises: 0c4f4a471bc9
Create Date: 2026-02-02 21:20:43.262421

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e275df77f298'
down_revision: Union[str, Sequence[str], None] = '0c4f4a471bc9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - convert board_index from 1-based to 0-based.

    The game code uses 0-based indexing (0-39) but the spaces table
    was populated with 1-based board_index values (1-40). This caused
    a mismatch where landing on position 34 would look up board_index=34
    which was "Curtin Uni" instead of "The Casino".
    """
    # Update spaces table: subtract 1 from all board_index values
    # This converts from 1-based (1-40) to 0-based (0-39)
    op.execute("UPDATE spaces SET board_index = board_index - 1")


def downgrade() -> None:
    """Downgrade schema - revert to 1-based indexing."""
    # Revert spaces table: add 1 back to all board_index values
    op.execute("UPDATE spaces SET board_index = board_index + 1")
