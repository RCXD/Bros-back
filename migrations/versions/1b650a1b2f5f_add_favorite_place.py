"""add place table

Revision ID: 1b650a1b2f5f
Revises: 0a0aaa28c4fc
Create Date: 2024-07-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "1b650a1b2f5f"
down_revision = "0a0aaa28c4fc"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "place",
        sa.Column("place_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("point", sa.Float(), nullable=True),
        sa.Column("radius", sa.Float(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("place_id"),
    )
    op.create_index(
        "idx_favorite_place_user", "place", ["user_id"], unique=False
    )
    op.create_index(
        "idx_favorite_place_location", "place", ["lat", "lon"], unique=False
    )


def downgrade():
    op.drop_index("idx_favorite_place_location", table_name="place")
    op.drop_index("idx_favorite_place_user", table_name="place")
    op.drop_table("place")
