"""Convert place to static geometry-focused model

Revision ID: d79d5b6c7e9a
Revises: 1b650a1b2f5f
Create Date: 2024-08-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision = "d79d5b6c7e9a"
down_revision = "1b650a1b2f5f"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("place") as batch_op:
        for idx in ("idx_favorite_place_user", "idx_favorite_place_location"):
            try:
                batch_op.drop_index(idx)
            except Exception:
                pass
        for fk in ("place_ibfk_1", "fk_place_user_id_users"):
            try:
                batch_op.drop_constraint(fk, type_="foreignkey")
            except Exception:
                pass
        for col in ("user_id", "point", "radius", "is_public"):
            try:
                batch_op.drop_column(col)
            except Exception:
                pass
        batch_op.add_column(sa.Column("alt_name", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("tags", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("geom", mysql.GEOMETRY(srid=4326), nullable=True))

    op.create_index("idx_place_lat_lon", "place", ["lat", "lon"])
    op.create_index(
        "idx_place_geom_spatial",
        "place",
        ["geom"],
        mysql_prefix="SPATIAL",
    )

    # populate geom from existing lat/lon if possible
    try:
        op.execute(
            sa.text(
                """
                UPDATE place
                SET geom = ST_SRID(ST_GeomFromText(CONCAT('POINT(', lon, ' ', lat, ')')), 4326)
                WHERE geom IS NULL AND lat IS NOT NULL AND lon IS NOT NULL
                """
            )
        )
    except Exception:
        # database may not support spatial functions; skip quietly
        pass


def downgrade():
    op.drop_index("idx_place_geom_spatial", table_name="place")
    op.drop_index("idx_place_lat_lon", table_name="place")
    with op.batch_alter_table("place") as batch_op:
        batch_op.drop_column("geom")
        batch_op.drop_column("tags")
        batch_op.drop_column("alt_name")
        batch_op.add_column(sa.Column("is_public", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("radius", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("point", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=False))
        batch_op.create_foreign_key(
            "fk_place_user_id_users", "users", ["user_id"], ["user_id"], ondelete="CASCADE"
        )

    op.create_index("idx_favorite_place_user", "place", ["user_id"])
    op.create_index("idx_favorite_place_location", "place", ["lat", "lon"])
