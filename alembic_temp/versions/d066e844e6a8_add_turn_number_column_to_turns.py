from alembic import op
import sqlalchemy as sa

revision = "d066e844e6a8"
down_revision = "1d20d306639e"
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("turns")]

    if "turn_number" not in columns:
        with op.batch_alter_table("turns") as batch:
            batch.add_column(
                sa.Column("turn_number", sa.Integer(), nullable=False, server_default="0")
            )

def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("turns")]

    if "turn_number" in columns:
        with op.batch_alter_table("turns") as batch:
            batch.drop_column("turn_number")
