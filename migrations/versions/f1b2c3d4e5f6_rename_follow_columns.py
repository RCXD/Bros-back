"""Rename Follow relationship columns.

Revision ID: f1b2c3d4e5f6
Revises: d79d5b6c7e9a
Create Date: 2025-11-21 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f1b2c3d4e5f6"
down_revision = "d79d5b6c7e9a"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("follow") as batch_op:
        batch_op.drop_constraint("unique_follow", type_="unique")
        batch_op.alter_column(
            "follower_id",
            new_column_name="from_user_id",
            existing_type=sa.Integer(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "following_id",
            new_column_name="to_user_id",
            existing_type=sa.Integer(),
            existing_nullable=False,
        )
        batch_op.create_unique_constraint(
            "unique_follow",
            ["from_user_id", "to_user_id"],
        )


def downgrade():
    with op.batch_alter_table("follow") as batch_op:
        batch_op.drop_constraint("unique_follow", type_="unique")
        batch_op.alter_column(
            "from_user_id",
            new_column_name="follower_id",
            existing_type=sa.Integer(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "to_user_id",
            new_column_name="following_id",
            existing_type=sa.Integer(),
            existing_nullable=False,
        )
        batch_op.create_unique_constraint(
            "unique_follow",
            ["follower_id", "following_id"],
        )
