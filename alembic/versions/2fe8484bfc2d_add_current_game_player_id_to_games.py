"""add current_game_player_id to games

Revision ID: 2fe8484bfc2d
Revises: d066e844e6a8
Create Date: 2026-01-24

"""
from alembic import op
import sqlalchemy as sa

revision = "2fe8484bfc2d"
down_revision = "d066e844e6a8"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("games")]

    if "current_game_player_id" not in columns:
        with op.batch_alter_table("games") as batch:
            batch.add_column(
                sa.Column("current_game_player_id", sa.Integer(), nullable=True)
            )
            batch.create_foreign_key(
                "fk_games_current_game_player_id",
                "game_players",
                ["current_game_player_id"],
                ["game_player_id"],
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("games")]

    if "current_game_player_id" in columns:
        with op.batch_alter_table("games") as batch:
            batch.drop_constraint("fk_games_current_game_player_id", type_="foreignkey")
            batch.drop_column("current_game_player_id")
