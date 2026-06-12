"""split the single haystack into two hazard-keyed haystacks ("Max's rule")

Replaces game_players.has_haystack / haystack_used with haystack_pasture
(offsets Local Drought / Drought on ALL Stations) and haystack_irrigated
(offsets Bore Dries Up). Existing generic haystacks are migrated to the
pasture haystack, which is the common case.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-12 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('game_players', sa.Column(
        'haystack_pasture', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('game_players', sa.Column(
        'haystack_irrigated', sa.Boolean(), nullable=False, server_default=sa.false()))
    # Migrate existing generic haystacks to the pasture haystack.
    op.execute("UPDATE game_players SET haystack_pasture = true WHERE has_haystack = true")
    op.drop_column('game_players', 'has_haystack')
    op.drop_column('game_players', 'haystack_used')


def downgrade() -> None:
    op.add_column('game_players', sa.Column(
        'has_haystack', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('game_players', sa.Column(
        'haystack_used', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE game_players SET has_haystack = true "
               "WHERE haystack_pasture = true OR haystack_irrigated = true")
    op.drop_column('game_players', 'haystack_pasture')
    op.drop_column('game_players', 'haystack_irrigated')
