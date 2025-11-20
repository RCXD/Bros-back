import json

from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import SQLAlchemyError

from apps.config.server import db
from apps.place.models import Place, func
from apps.place.utils import _build_geom
from datetime import datetime
from apps.admin.views import admin_required

bp = Blueprint("place", __name__)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

def _store_place_area(place, geom_obj, lat=None, lon=None):
    """Prefer spatial geometry column when available, fall back to JSON edges."""
    lat_val = lat if lat is not None else getattr(place, "lat", None)
    lon_val = lon if lon is not None else getattr(place, "lon", None)
    has_geom_column = hasattr(Place, "geom")
    has_edges_column = hasattr(place, "edges")

    if geom_obj is None:
        if has_geom_column:
            place.geom = _build_geom(lat_val, lon_val)
        if has_edges_column:
            place.edges = None
        return

    if has_geom_column:
        geom_value = _build_geom(lat_val, lon_val, geom_obj)
        if geom_value is not None:
            place.geom = geom_value
            if has_edges_column:
                place.edges = None
            return

    if has_edges_column:
        place.edges = geom_obj
        if has_geom_column:
            place.geom = None

def _parse_float(value, field, min_value=None, max_value=None):
    if value is None:
        return None, None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None, f"{field} must be a number"
    if min_value is not None and numeric < min_value:
        return None, f"{field} must be >= {min_value}"
    if max_value is not None and numeric > max_value:
        return None, f"{field} must be <= {max_value}"
    return numeric, None


def _validate_place_payload(data, partial=False):
    errors = []
    payload = {}

    if (not partial) or ("name" in data):
        name = (data.get("name") or "").strip()
        if not name:
            errors.append("name is required")
        else:
            payload["name"] = name

    if (not partial) or ("lat" in data):
        lat_raw = data.get("lat")
        lat, error = _parse_float(lat_raw, "lat", -90, 90)
        if error:
            errors.append(error)
        elif lat is None:
            errors.append("lat is required")
        else:
            payload["lat"] = lat

    if (not partial) or ("lon" in data):
        lon_raw = data.get("lon")
        lon, error = _parse_float(lon_raw, "lon", -180, 180)
        if error:
            errors.append(error)
        elif lon is None:
            errors.append("lon is required")
        else:
            payload["lon"] = lon

    if "alt_name" in data:
        payload["alt_name"] = (data.get("alt_name") or "").strip() or None

    if "description" in data:
        payload["description"] = data.get("description")

    if "tags" in data:
        tags = data.get("tags")
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except (TypeError, json.JSONDecodeError):
                errors.append("tags must be valid JSON when provided as string")
                tags = None
        if tags is not None and not isinstance(tags, (list, dict)):
            errors.append("tags must be a JSON object or array")
        else:
            payload["tags"] = tags

    if "geom" in data:
        geom = data.get("geom")
        geom_error = _validate_geojson(geom)
        if geom_error:
            errors.append(geom_error)
        else:
            payload["geom"] = geom

    return payload, errors


def _validate_geojson(geom):
    if geom is None:
        return None
    if not isinstance(geom, dict):
        return "geom must be a GeoJSON object"
    if "type" not in geom or "coordinates" not in geom:
        return "geom must contain type and coordinates"
    if not _coordinates_are_numeric(geom.get("coordinates")):
        return "geom coordinates must be numeric"
    return None


def _coordinates_are_numeric(coords):
    if isinstance(coords, (int, float)):
        return True
    if isinstance(coords, list):
        return all(_coordinates_are_numeric(c) for c in coords)
    return False


@bp.post("")
@jwt_required()
def create_place():
    data = request.get_json() or {}
    payload, errors = _validate_place_payload(data)
    if errors:
        return jsonify({"message": "Invalid input", "errors": errors}), 400

    geom_obj = payload.pop("geom", None)
    place = Place(**payload)
    _store_place_area(place, geom_obj, place.lat, place.lon)
    try:
        db.session.add(place)
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        return jsonify({"message": "Failed to save place", "error": str(exc)}), 400

    return jsonify({"message": "Place created", "place": place.to_dict()}), 201


@bp.get("")
@jwt_required(optional=True)
def list_places():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", DEFAULT_PAGE_SIZE, type=int)
    per_page = max(1, min(per_page, MAX_PAGE_SIZE))

    query = Place.query

    name_query = (request.args.get("name") or "").strip()
    if name_query:
        query = query.filter(Place.name.ilike(f"%{name_query}%"))

    tag_value = request.args.get("tag")
    if tag_value:
        query = query.filter(Place.tags.contains(tag_value))

    bbox = request.args.get("bbox")
    if bbox:
        try:
            min_lon, min_lat, max_lon, max_lat = [float(x) for x in bbox.split(",")]
            if min_lat > max_lat or min_lon > max_lon:
                raise ValueError
        except ValueError:
            return jsonify({"message": "bbox must be four comma-separated floats: min_lon,min_lat,max_lon,max_lat"}), 400
        query = query.filter(
            Place.lat.between(min_lat, max_lat),
            Place.lon.between(min_lon, max_lon),
        )

    query = query.order_by(Place.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return (
        jsonify(
            {
                "items": [place.to_dict() for place in pagination.items],
                "total": pagination.total,
                "pages": pagination.pages,
                "page": page,
                "per_page": per_page,
            }
        ),
        200,
    )


@bp.get("/<int:place_id>")
@jwt_required(optional=True)
def get_place(place_id):
    place = Place.query.get(place_id)
    if not place:
        return jsonify({"message": "Place not found"}), 404
    return jsonify({"place": place.to_dict()}), 200


@bp.put("/<int:place_id>")
@jwt_required()
def update_place(place_id):
    error = admin_required()
    if error:
        return error
    place = Place.query.get(place_id)
    if not place:
        return jsonify({"message": "Place not found"}), 404

    data = request.get_json() or {}
    payload, errors = _validate_place_payload(data, partial=True)
    if errors:
        return jsonify({"message": "Invalid input", "errors": errors}), 400

    geom_obj = payload.pop("geom", None) if "geom" in payload else None
    for key, value in payload.items():
        setattr(place, key, value)

    if ("geom" in data) or ("lat" in payload) or ("lon" in payload):
        if "geom" in data and data.get("geom") is None:
            if hasattr(place, "geom"):
                place.geom = None
            if hasattr(place, "edges"):
                place.edges = None
        else:
            lat_for_geom = payload.get("lat", place.lat)
            lon_for_geom = payload.get("lon", place.lon)
            _store_place_area(place, geom_obj, lat_for_geom, lon_for_geom)

    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        return jsonify({"message": "Failed to update place", "error": str(exc)}), 400

    return jsonify({"message": "Place updated", "place": place.to_dict()}), 200


@bp.delete("/<int:place_id>")
@jwt_required()
def delete_place(place_id):
    error = admin_required()
    if error:
        return error
    place = Place.query.get(place_id)
    if not place:
        return jsonify({"message": "Place not found"}), 404

    try:
        db.session.delete(place)
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        return jsonify({"message": "Failed to delete place", "error": str(exc)}), 400

    return jsonify({"message": "Place deleted"}), 200


def place_to_dict(place):
    geom = None
    if place.geom is not None:
        # ST_AsGeoJSON 또는 to_shape 사용
        geom = current_app.session.scalar(func.ST_AsGeoJSON(place.geom))
        # 또는: geom = json.loads(db.session.scalar(func.ST_AsGeoJSON(place.geom)))
    return {
        "id": place.id,
        "name": place.name,
        "display_name": place.display_name,
        "description": place.description,
        "tags": place.tags or [],
        "geom": geom and json.loads(geom) or None,
        "source": place.source,
        "is_active": place.is_active,
        "created_by": place.created_by,
        "created_at": place.created_at.isoformat(),
        "updated_at": place.updated_at.isoformat(),
    }

@bp.route("/search", methods=["GET"])
def search_places():
    # 프론트에서 /place/search?q=키워드&bbox=lonmin,latmin,lonmax,latmax&page=1&per_page=20&tag=park
    q = request.args.get("q", "").strip()
    bbox = request.args.get("bbox")
    tag = request.args.get("tag")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))

    query = Place.query.filter(Place.is_active == True)

    if q:
        # 부분검색: 이름 또는 display_name
        query = query.filter(func.lower(Place.name).like(f"%{q.lower()}%") | func.lower(Place.display_name).like(f"%{q.lower()}%"))

    if tag:
        # tags 배열에 tag 포함 검사 (Postgres)
        query = query.filter(func.array_to_string(Place.tags, ',').ilike(f"%{tag}%"))
        # 또는: Place.tags.any(tag) if tags is Postgres ARRAY

    if bbox:
        try:
            lonmin, latmin, lonmax, latmax = map(float, bbox.split(","))
            envelope = func.ST_MakeEnvelope(lonmin, latmin, lonmax, latmax, 4326)
            query = query.filter(func.ST_Intersects(Place.geom, envelope))
        except Exception:
            pass

    total = query.count()
    places = query.order_by(Place.id.desc()).offset((page-1)*per_page).limit(per_page).all()

    results = [place_to_dict(p) for p in places]
    return jsonify({"results": results, "meta": {"page": page, "per_page": per_page, "total": total}}), 200
