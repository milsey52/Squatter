"""rename board-index columns to say what they store

game_players.current_space_id and game_players.restock_block_marker_space_id
always held a board index (0-43), not a spaces.space_id foreign key —
unlike movements.start_space_id/end_space_id, which are real FKs. Rename
them so the schema stops lying.

Revision ID: c9d0e1f2a3b4
Revises: b7c8d9e0f1a2
Create Date: 2026-06-11 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c9d0e1f2a3b4'
down_revision: Union[str, Sequence[str], None] = 'b7c8d9e0f1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


RENAMES = [
    ('current_space_id', 'current_board_index'),
    ('restock_block_marker_space_id', 'restock_block_marker_board_index'),
]


def _conditional_rename(old: str, new: str) -> None:
    """Rename only when the old column exists. Some databases drifted
    (columns created by scripts/fix_schema_drift.py under the new name
    rather than by migrations under the old one), so an unconditional
    rename can hit a missing column."""
    op.execute(f"""
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'game_players' AND column_name = '{old}'
          ) THEN
            ALTER TABLE game_players RENAME COLUMN {old} TO {new};
          END IF;
        END $$;
    """)


def upgrade() -> None:
    if op.get_bind().dialect.name == 'postgresql':
        for old, new in RENAMES:
            _conditional_rename(old, new)
    else:
        for old, new in RENAMES:
            op.alter_column('game_players', old, new_column_name=new)


def downgrade() -> None:
    if op.get_bind().dialect.name == 'postgresql':
        for old, new in RENAMES:
            _conditional_rename(new, old)
    else:
        for old, new in RENAMES:
            op.alter_column('game_players', new, new_column_name=old)
