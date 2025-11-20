from sqlalchemy.types import UserDefinedType


class MySQLGeometry(UserDefinedType):
    """Minimal replacement for the removed sqlalchemy.dialects.mysql.GEOMETRY."""

    cache_ok = True

    def __init__(self, geometry_type=None, srid=None):
        self.geometry_type = geometry_type.upper() if geometry_type else None
        self.srid = srid

    def get_col_spec(self, **kw):
        geom_type = self.geometry_type or "GEOMETRY"
        spec = geom_type
        if self.srid is not None:
            spec = f"{spec} SRID {int(self.srid)}"
        return spec

    def bind_expression(self, bindvalue):
        return bindvalue

    def column_expression(self, col):
        return col


GEOMETRY = MySQLGeometry

