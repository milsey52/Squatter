"""add multiplayer support

Revision ID: b1c2d3e4f5g6
Revises: a1b2c3d4e5f6
Create Date: 2026-01-25

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime, timedelta

revision = "b1c2d3e4f5g6"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    # Add game_code column to games table
    op.add_column("games", sa.Column("game_code", sa.String(6), nullable=True))

    # Add max_players column to games table
    op.add_column("games", sa.Column("max_players", sa.Integer(), nullable=False, server_default="6"))

    # Add is_ready column to game_players table
    op.add_column("game_players", sa.Column("is_ready", sa.Boolean(), nullable=False, server_default=sa.text("0")))

    # Create game_sessions table
    op.create_table(
        "game_sessions",
        sa.Column("session_token", sa.String(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.game_id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now())
    )

    # Backfill game codes for existing games
    # Generate simple codes for existing games (they can be regenerated if needed)
    conn = op.get_bind()
    # For SQLite, we'll use a simple pattern to backfill codes
    conn.execute(sa.text("""
        UPDATE games
        SET game_code = UPPER(SUBSTR(HEX(RANDOMBLOB(4)), 1, 6))
        WHERE game_code IS NULL
    """))

    # Now make game_code NOT NULL
    # Note: SQLite doesn't support ALTER COLUMN, so we need to be careful
    # The column was added as nullable, backfilled, and now we rely on application to enforce NOT NULL
    # For production with PostgreSQL, you would use:
    # op.alter_column("games", "game_code", nullable=False)

    # Create unique index on game_code
    op.create_index("ix_games_game_code", "games", ["game_code"], unique=True)

    # Note: SQLite doesn't support ALTER COLUMN to drop server defaults
    # Server defaults will remain in the schema (harmless for SQLite)


def downgrade():
    # Drop index
    op.drop_index("ix_games_game_code", "games")

    # Drop columns
    op.drop_column("games", "game_code")
    op.drop_column("games", "max_players")
    op.drop_column("game_players", "is_ready")

    # Drop table
    op.drop_table("game_sessions")
