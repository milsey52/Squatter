"""add pending_actions table

Revision ID: a1b2c3d4e5f6
Revises: 2fe8484bfc2d
Create Date: 2026-01-24

"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "2fe8484bfc2d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pending_actions",
        sa.Column("pending_action_id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.game_id"), nullable=False),
        sa.Column("turn_id", sa.Integer(), sa.ForeignKey("turns.turn_id"), nullable=False),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.asset_id")),
        sa.Column("active_player_id", sa.Integer(), sa.ForeignKey("game_players.game_player_id")),
        sa.Column("action_data", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime()),
    )


def downgrade():
    op.drop_table("pending_actions")
