import json
import os
import requests
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required
from sqlalchemy import cast, desc, asc
from sqlalchemy.exc import SQLAlchemyError

from apps.config.server import db
from apps.place.models import Place, PlaceCategory, PlaceType, func
from apps.place.utils import _build_bbox
from apps.admin.views import admin_required

bp = Blueprint("place", __name__)


@bp.get("/api_info")
def api_info():
    """
    장소 API 정보 제공 (개발용)
    """
    info_path = os.path.join(os.path.dirname(__file__), "info.json")
    with open(info_path, "r", encoding="utf-8") as f:
        info = json.load(f)
    return jsonify(info), 200


DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
NOMINATIM_HEADERS = {
    "User-Agent": "BrosPlaceSearch/1.0 (+https://bros.app)",
    "Accept-Language": "ko",
}
DEFAULT_POINT_RADIUS_METERS = 500
MAX_POINT_RADIUS_METERS = 50000


def _store_place_area(place, geom_obj, lat=None, lon=None):
    """Prefer spatial geometry column when available, fall back to JSON edges."""
    lat_val = lat if lat is not None else getattr(place, "lat", None)
    lon_val = lon if lon is not None else getattr(place, "lon", None)
    has_geom_column = hasattr(Place, "geom")
    has_edges_column = hasattr(place, "edges")
    geom_type = None
    if isinstance(geom_obj, dict):
        geom_type_raw = geom_obj.get("type")
        if isinstance(geom_type_raw, str):
            geom_type = geom_type_raw.strip().lower()
    if geom_type in {"polygon", "multipolygon"}:
        stored_geom = _build_bbox(None, None, geom_obj) if has_geom_column else None
        if has_geom_column:
            place.geom = _build_bbox(lon_val, lat_val)
        if has_edges_column:
            place.edges = None
        return

    if has_geom_column:
        geom_value = _build_bbox(lon_val, lat_val, geom_obj)
        if geom_value is not None:
            place.geom = geom_value
            if has_edges_column:
                place.edges = None
            return

    if has_edges_column:
        place.edges = geom_obj
        if has_geom_column:
            place.geom = None


def _set_place_coordinate(place, lat, lon):
    place.coordinate = _place_lat_lon(lat, lon)


def _place_lat_lon(place):
    lat, lon = _set_place_coordinate(getattr(place, "coordinate", None))
    if lat is None and hasattr(place, "lat"):
        lat = getattr(place, "lat")
    if lon is None and hasattr(place, "lon"):
        lon = getattr(place, "lon")
    return lat, lon


def _lat_column():
    return func.ST_Y(Place.coordinate)


def _lon_column():
    return func.ST_X(Place.coordinate)


def _first_segment(text):
    if not text:
        return None
    segment = text.split(",", 1)[0].strip()
    return segment or text.strip()


def _reverse_geojson_feature(data):
    if not isinstance(data, dict):
        return None
    if data.get("type") == "FeatureCollection":
        features = data.get("features") or []
        return features[0] if features else None
    if data.get("type") == "Feature":
        return data
    return None


def _bbox_to_geojson_polygon(bbox, order_hint="lonlat"):
    """Convert bbox array into a GeoJSON Polygon respecting the indicated coordinate order."""
    if not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
        return None

    def _build(order):
        try:
            coords = [float(x) for x in bbox[:4]]
        except (TypeError, ValueError):
            return None
        if order == "latlon":
            min_lat, max_lat, min_lon, max_lon = coords
        else:
            min_lon, min_lat, max_lon, max_lat = coords
        if min_lon >= max_lon or min_lat >= max_lat:
            return None
        ring = [
            [min_lon, min_lat],
            [max_lon, min_lat],
            [max_lon, max_lat],
            [min_lon, max_lat],
            [min_lon, min_lat],
        ]
        return {"type": "Polygon", "coordinates": [ring]}

    polygon = _build(order_hint)
    if polygon is not None:
        return polygon
    alternate = "latlon" if order_hint == "lonlat" else "lonlat"
    return _build(alternate)


def _compose_reverse_tags(properties):
    tags = {}
    address = properties.get("address") if isinstance(properties, dict) else None
    if isinstance(address, dict):
        tags["address"] = address
    extratags = properties.get("extratags") if isinstance(properties, dict) else None
    if isinstance(extratags, dict) and extratags:
        tags["extratags"] = extratags
    if isinstance(properties, dict):
        for key in ("category", "type", "addresstype"):
            value = properties.get(key)
            if value:
                tags[key] = value
        place_id = properties.get("place_id") or properties.get("osm_id")
        if place_id:
            tags["nominatim_place_id"] = place_id
    return tags


def _reverse_feature_to_payload(feature):
    if not isinstance(feature, dict):
        return None
    properties = feature.get("properties") or {}
    geometry = feature.get("geometry") or {}
    coords = geometry.get("coordinates") or []
    if not isinstance(coords, (list, tuple)) or len(coords) < 2:
        return None
    lon, lat = coords[0], coords[1]
    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        return None
    display_name = (properties.get("display_name") or "").strip()
    name_candidate = _first_segment(display_name) or properties.get("name")
    name = _truncate(name_candidate or display_name or "Unnamed")
    alt_name = _truncate(display_name) if display_name else None
    tags = _compose_reverse_tags(properties)
    bbox = feature.get("bbox") if isinstance(feature, dict) else None
    if bbox:
        tags["bbox"] = bbox
    tags["source"] = "reverse"
    tags["nominatim_raw_properties"] = properties
    return {
        "name": name,
        "alt_name": alt_name,
        "lat": lat,
        "lon": lon,
        "description": display_name or properties.get("name"),
        "tags": tags,
    }


def _legacy_reverse_payload(data, fallback_lat=None, fallback_lon=None):
    if not isinstance(data, dict):
        return None
    lat = data.get("lat") or fallback_lat
    lon = data.get("lon") or data.get("lng") or fallback_lon
    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        return None
    display_name = (data.get("display_name") or "").strip()
    name_candidate = _first_segment(display_name) or data.get("name")
    name = _truncate(name_candidate or display_name or "Unnamed")
    alt_name = _truncate(display_name) if display_name else None
    tags = {}
    address = data.get("address")
    if isinstance(address, dict):
        tags["address"] = address
    if data.get("type"):
        tags["type"] = data.get("type")
    if data.get("category"):
        tags["category"] = data.get("category")
    tags["source"] = "reverse"
    tags["nominatim_raw_properties"] = data
    bbox = data.get("bbox") if isinstance(data, dict) else None
    if bbox:
        tags["bbox"] = bbox
    return {
        "name": name,
        "alt_name": alt_name,
        "lat": lat,
        "lon": lon,
        "description": display_name or data.get("name"),
        "tags": tags,
    }


def _normalize_reverse_response(data, fallback_lat=None, fallback_lon=None):
    feature = _reverse_geojson_feature(data)
    geom = None
    if feature:
        payload = _reverse_feature_to_payload(feature)
        bbox_geom = _bbox_to_geojson_polygon(feature.get("bbox"))
        if bbox_geom:
            geom = bbox_geom
        else:
            geometry = feature.get("geometry") if isinstance(feature, dict) else None
            if geometry and _validate_geojson(geometry) is None:
                geom = geometry
        raw_origin = data
    else:
        payload = _legacy_reverse_payload(data, fallback_lat, fallback_lon)
        bbox_geom = _bbox_to_geojson_polygon(data.get("bbox"))
        if bbox_geom:
            geom = bbox_geom
        raw_origin = data
    return payload, raw_origin, geom


def _find_existing_place(name, lat, lon, epsilon=0.0005):
    if not name:
        return None
    lowered = name.lower()
    return (
        Place.query.filter(
            func.lower(Place.name) == lowered,
            _lat_column().between(lat - epsilon, lat + epsilon),
            _lon_column().between(lon - epsilon, lon + epsilon),
        )
        .order_by(Place.updated_at.desc())
        .first()
    )


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
    error = admin_required()
    if error:
        return error
    data = request.get_json() or {}
    payload, errors = _validate_place_payload(data)
    if errors:
        return jsonify({"message": "Invalid input", "errors": errors}), 400

    geom_obj = payload.pop("geom", None)
    lat_val = payload.pop("lat", None)
    lon_val = payload.pop("lon", None)
    place = Place(**payload)
    _set_place_coordinate(place, lat_val, lon_val)
    _store_place_area(place, geom_obj, lat_val, lon_val)
    try:
        db.session.add(place)
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        return jsonify({"message": "Failed to save place", "error": str(exc)}), 400

    pin = place_to_pin(place)
    return jsonify({"message": "Place created", "pin": pin}), 201


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

    query = query.order_by(Place.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return (
        jsonify(
            {
                "items": [place_to_pin(place) for place in pagination.items],
                "total": pagination.total,
                "pages": pagination.pages,
                "page": page,
                "per_page": per_page,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev,
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
    return jsonify({"place": place_to_pin(place)}), 200


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

    return jsonify({"message": "Place updated", "pin": place_to_pin(place)}), 200


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
    """Return a frontend-friendly structure without assuming optional columns exist."""
    data = place.to_dict()
    data["id"] = data.get("place_id")
    data["display_name"] = data.get("alt_name") or data.get("name")
    if data.get("tags") is None:
        data["tags"] = []
    data["geom"] = None
    data["source"] = "place"
    data.setdefault("description", None)
    return data


def _normalize_tags(tags):
    if tags is None:
        return {}
    if isinstance(tags, str):
        try:
            return json.loads(tags) or {}
        except (TypeError, json.JSONDecodeError):
            return {}
    if isinstance(tags, (dict, list)):
        return tags
    return {}


def _derive_pin_type(properties, extratags=None):
    """
    properties: nominatim 'properties' dict
    extratags: nominatim 'extratags'
    """

    category = (properties.get("category") or "").lower()
    ptype = (properties.get("type") or "").lower()
    addresstype = (properties.get("addresstype") or "").lower()

    if extratags is None:
        extratags = properties.get("extratags", {}) or {}

    extraclass = (extratags.get("class") or "").lower()
    extratype = (extratags.get("type") or "").lower()

    # -----------------------------
    # 1. 정밀 매핑 (category + type)
    # -----------------------------
    CATEGORY_TYPE_MAP = {
        ("amenity", "cafe"): "cafe",
        ("amenity", "fast_food"): "restaurant",
        ("amenity", "restaurant"): "restaurant",
        ("amenity", "parking"): "parking",
        ("amenity", "school"): "school",
        ("amenity", "hospital"): "hospital",
        ("amenity", "pharmacy"): "pharmacy",
        ("shop", "convenience"): "convenience",
        ("shop", "supermarket"): "shopping",
        ("shop", "mall"): "shopping",
        ("shop", "clothes"): "shopping",
        ("place", "house"): "house",
        ("place", "city"): "city",
        ("place", "town"): "city",
        ("place", "village"): "region",
        ("building", "house"): "house",
        ("building", "residential"): "house",
        ("building", "apartments"): "house",
        ("highway", "bus_stop"): "transport",
        ("highway", "crossing"): "traffic",
        ("highway", "traffic_signals"): "traffic",
    }


def _build_label(name=None, alt_name=None, display_name=None):
    for value in (alt_name, name, display_name):
        if value:
            return value
    return None


def place_to_pin(place):
    raw = place.to_dict() if hasattr(place, "to_dict") else dict(place)
    label = _build_label(raw.get("name"), raw.get("alt_name"), raw.get("display_name"))
    tags = _normalize_tags(raw.get("tags"))
    pin_type = _derive_pin_type(label, tags)
    return {
        "id": raw.get("place_id") or raw.get("id"),
        "placeId": raw.get("place_id") or raw.get("id"),
        "name": raw.get("name"),
        "label": label,
        "lat": raw.get("lat"),
        "lng": raw.get("lon"),
        "type": pin_type,
        "tags": tags,
        "source": "place",
        "createdAt": raw.get("created_at"),
        "updatedAt": raw.get("updated_at"),
        "raw": raw,
    }


def _resolve_coordinates(item):
    try:
        lat = float(item.get("lat"))
        lon = float(item.get("lon"))
        return lat, lon
    except (TypeError, ValueError):
        return None, None


def _apply_point_radius_filter(query, center, radius_meters):
    if not center or radius_meters is None:
        return query
    lat, lon = center
    radius_meters = max(1.0, min(float(radius_meters), MAX_POINT_RADIUS_METERS))
    point_wkt = f"POINT({lon} {lat})"
    point_geom = func.ST_GeomFromText(point_wkt, 4326)
    distance_expr = func.ST_Distance_Sphere(Place.coordinate, point_geom)
    return query.filter(
        Place.coordinate.isnot(None),
        distance_expr <= radius_meters,
    )


def _build_filtered_query(search_text, tag, point_filter=None):
    query = Place.query
    if search_text:
        lowered = f"%{search_text.lower()}%"
        query = query.filter(
            func.lower(Place.name).like(lowered)
            | func.lower(Place.alt_name).like(lowered)
        )
    if tag:
        query = query.filter(
            Place.tags.isnot(None),
            func.lower(cast(Place.tags, db.Text)).like(f"%{tag.lower()}%"),
        )
    if point_filter:
        query = _apply_point_radius_filter(query, point_filter[:2], point_filter[2])
    return query


def _truncate(value, limit=255):
    if not isinstance(value, str):
        return value
    return value[:limit]


def _normalize_nominatim_item(item):
    if not isinstance(item, dict):
        return None
    lat, lon = _resolve_coordinates(item)
    if lat is None or lon is None:
        return None
    primary_name = (
        (item.get("namedetails") or {}).get("name")
        or item.get("name")
        or item.get("display_name")
    )
    if not primary_name:
        return None
    alt_name = item.get("display_name")
    tags = item.get("extratags")
    if not isinstance(tags, dict):
        tags = {}
    for key in ("type", "class"):
        value = item.get(key)
        if value and key not in tags:
            tags[key] = value
    bbox = item.get("boundingbox")
    if bbox:
        try:
            lonmin, latmin, lonmax, latmax = map(float, bbox.split(","))
            envelope = func.ST_MakeEnvelope(lonmin, latmin, lonmax, latmax, 4326)
            query = query.filter(func.ST_Intersects(Place.geom, envelope))
        except Exception:
            pass


def _fetch_nominatim_places(search_text, limit):
    params = {
        "format": "json",
        "q": search_text,
        "addressdetails": 1,
        "namedetails": 1,
        "extratags": 1,
        "limit": limit,
    }
    try:
        resp = requests.get(
            NOMINATIM_SEARCH_URL, params=params, headers=NOMINATIM_HEADERS, timeout=5
        )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []
    except requests.RequestException as exc:
        current_app.logger.warning("nominatim search failed", exc_info=exc)
    except ValueError:
        current_app.logger.warning("invalid JSON from nominatim response")
    return []


def _place_exists_nearby(name, lat, lon, epsilon=0.0005):
    lowered = name.lower()
    return (
        Place.query.filter(
            func.lower(Place.name) == lowered,
            _lat_column().between(lat - epsilon, lat + epsilon),
            _lon_column().between(lon - epsilon, lon + epsilon),
        ).first()
        is not None
    )


def _ingest_nominatim_places(search_text, limit):
    raw_items = _fetch_nominatim_places(search_text, limit)
    normalized = []
    for item in raw_items:
        payload = _normalize_nominatim_item(item)
        if payload is not None:
            normalized.append(payload)
    if not normalized:
        return False, [], raw_items, False

    inserted = False
    for payload in normalized:
        if _place_exists_nearby(payload["name"], payload["lat"], payload["lon"]):
            continue
        lat_val = payload.get("lat")
        lon_val = payload.get("lon")
        place = Place(
            name=payload["name"],
            alt_name=payload.get("alt_name"),
            description=payload.get("description"),
            tags=payload.get("tags"),
        )
        _set_place_coordinate(place, lat_val, lon_val)
        _store_place_area(place, payload.get("geom"), lat_val, lon_val)
        db.session.add(place)
        inserted = True
    if not inserted:
        return False, normalized, raw_items, False
    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.error(
            "failed to persist nominatim search results", exc_info=exc
        )
        return False, normalized, raw_items, True
    return True, normalized, raw_items, False


def _serialize_transient_place(payload):
    tags = (
        payload.get("tags") if isinstance(payload.get("tags"), (dict, list)) else None
    )
    raw = {
        "place_id": None,
        "name": payload.get("name"),
        "alt_name": payload.get("alt_name"),
        "display_name": payload.get("alt_name") or payload.get("name"),
        "description": payload.get("description"),
        "tags": tags,
        "lat": payload.get("lat"),
        "lon": payload.get("lon"),
        "created_at": None,
        "updated_at": None,
    }
    return {
        "id": None,
        "placeId": None,
        "name": payload.get("name"),
        "label": payload.get("alt_name") or payload.get("name"),
        "lat": payload.get("lat"),
        "lng": payload.get("lon"),
        "type": _derive_pin_type(tags or {}, None),
        "tags": tags or {},
        "source": "nominatim",
        "createdAt": None,
        "updatedAt": None,
        "raw": raw,
    }


@bp.get("/search")
def search_places():
    q = (request.args.get("q") or "").strip()
    tag = (request.args.get("tag") or "").strip() or None
    lat_raw = request.args.get("lat")
    lon_raw = request.args.get("lon") or request.args.get("lng")
    radius_raw = request.args.get("radius")
    point_filter = None
    if lat_raw or lon_raw or radius_raw:
        if lat_raw is None or lon_raw is None:
            return (
                jsonify({"message": "lat and lon are required for radius search"}),
                400,
            )
        lat, lat_err = _parse_float(lat_raw, "lat", -90, 90)
        lon, lon_err = _parse_float(lon_raw, "lon", -180, 180)
        radius_value = (
            radius_raw if radius_raw is not None else DEFAULT_POINT_RADIUS_METERS
        )
        radius, radius_err = _parse_float(
            radius_value, "radius", 1, MAX_POINT_RADIUS_METERS
        )
        if lat_err or lon_err or radius_err:
            return jsonify({"message": lat_err or lon_err or radius_err}), 400
        point_filter = (lat, lon, radius)

    try:
        page = int(request.args.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    page = max(page, 1)
    print(page)
    try:
        per_page = int(request.args.get("per_page", DEFAULT_PAGE_SIZE))
    except (TypeError, ValueError):
        per_page = DEFAULT_PAGE_SIZE
    per_page = max(1, min(per_page, MAX_PAGE_SIZE))

    query = _build_filtered_query(q, tag, point_filter=point_filter)
    total = query.count()
    places = (
        query.order_by(Place.updated_at.desc(), Place.place_id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    print(places)
    results = [place_to_pin(p) for p in places]
    print(results)

    results = [place_to_dict(p) for p in places]
    if not results and q and page == 1 and tag is None and point_filter is None:
        _, normalized, _, db_error = _ingest_nominatim_places(q, per_page)
        if normalized:
            results = [_serialize_transient_place(payload) for payload in normalized]
            total = len(results)
            if db_error:
                current_app.logger.warning(
                    "Nominatim search results could not be persisted; returning transient data"
                )
    return (
        jsonify(
            {
                "results": results,
                "meta": {"page": page, "per_page": per_page, "total": total},
            }
        ),
        200,
    )


# ============================================================
# 반경 내 필터링 조회 API
# ============================================================


# 호환성
@bp.get("/reverse")
def reverse_geocode():
    """
    Reverse geocoding (Always save to DB except duplicates)
    GET /place/reverse?lat=37.57&lon=126.98
    """
    lat_raw = request.args.get("lat")
    lon_raw = request.args.get("lon") or request.args.get("lng")

    if lat_raw is None or lon_raw is None:
        return jsonify({"message": "lat and lon are required"}), 400

    lat, lat_err = _parse_float(lat_raw, "lat", -90, 90)
    lon, lon_err = _parse_float(lon_raw, "lon", -180, 180)
    if lat_err or lon_err:
        return jsonify({"message": lat_err or lon_err}), 400

    params = {
        "format": "jsonv2",
        "lat": lat,
        "lon": lon,
        "addressdetails": 1,
        "namedetails": 1,
        "extratags": 1,
        "polygon_geojson": 1,
    }

    try:
        resp = requests.get(
            NOMINATIM_REVERSE_URL,
            params=params,
            headers=NOMINATIM_HEADERS,
            timeout=5,
        )
        resp.raise_for_status()
        raw_data = resp.json()
    except requests.RequestException as exc:
        current_app.logger.error("Reverse nominatim failed", exc_info=exc)
        return jsonify({"message": "Reverse geocoding failed"}), 500

    payload, raw_origin, geom_obj = _normalize_reverse_response(
        raw_data, fallback_lat=lat, fallback_lon=lon
    )

    if payload is None:
        return jsonify({"message": "Invalid reverse data"}), 500

    name = payload.get("name") or payload.get("alt_name") or payload.get("description")
    if not name:
        return jsonify({"message": "No valid name in reverse result"}), 500

    duplicate = _find_existing_place(name, payload["lat"], payload["lon"])
    if duplicate:
        return jsonify({"place": place_to_pin(duplicate), "source": "existing"}), 200

    try:
        place = Place(
            name=payload.get("name"),
            alt_name=payload.get("alt_name"),
            description=payload.get("description"),
            tags=payload.get("tags"),
        )

        place.set_lat_lon(payload["lat"], payload["lon"])

        _store_place_area(place, geom_obj, payload["lat"], payload["lon"])
        print(place)
        db.session.add(place)
        db.session.commit()

        return jsonify({"place": place_to_pin(place), "source": "stored"}), 201

    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.error("Failed to save reverse place", exc_info=exc)

        tmp = _serialize_transient_place(payload)
        tmp["source"] = "reverse-db-error"
        return jsonify({"place": tmp}), 200


@bp.get("/nearby")
@jwt_required(optional=True)
def get_nearby_places():
    """
    기준 위치에서 반경 내 모든 정보 조회

    Query Parameters:
    - lat: 중심 위도 (필수)
    - lon: 중심 경도 (필수)
    - radius: 반경(m, 기본: 500, 최대: 50000)
    - sentiment: 정보 성격 필터 (positive/negative/neutral, 콤마 구분 가능)
    - post_filter: 게시글 연동 필터 (with_post/without_post/all, 기본: all)
    - sort: 정렬 방식 (recommendation_first/latest_first, 기본: recommendation_first)
    - type: 장소 타입 필터 (콤마 구분 가능, 예: pothole,restaurant)
    - page: 페이지 번호 (기본: 1)
    - per_page: 페이지당 개수 (기본: 20, 최대: 100)
    """
    # 필수 파라미터 검증
    lat_raw = request.args.get("lat")
    lon_raw = request.args.get("lon") or request.args.get("lng")

    if not lat_raw or not lon_raw:
        return jsonify({"message": "lat and lon are required"}), 400

    lat, lat_err = _parse_float(lat_raw, "lat", -90, 90)
    lon, lon_err = _parse_float(lon_raw, "lon", -180, 180)

    if lat_err or lon_err:
        return jsonify({"message": lat_err or lon_err}), 400

    # 반경
    radius_raw = request.args.get("radius", DEFAULT_POINT_RADIUS_METERS)
    radius, radius_err = _parse_float(radius_raw, "radius", 1, MAX_POINT_RADIUS_METERS)
    if radius_err:
        return jsonify({"message": radius_err}), 400

    # 정보 성격 필터 (positive/negative/neutral)
    sentiment_raw = request.args.get("sentiment", "").strip()
    sentiments = (
        [s.strip().lower() for s in sentiment_raw.split(",") if s.strip()]
        if sentiment_raw
        else []
    )

    # 게시글 연동 필터
    post_filter = request.args.get("post_filter", "all").strip().lower()
    if post_filter not in ("with_post", "without_post", "all"):
        post_filter = "all"

    # 정렬 방식
    sort = request.args.get("sort", "recommendation_first").strip().lower()
    if sort not in ("recommendation_first", "latest_first"):
        sort = "recommendation_first"

    # 타입 필터
    type_raw = request.args.get("type", "").strip()
    type_names = (
        [t.strip().lower() for t in type_raw.split(",") if t.strip()]
        if type_raw
        else []
    )

    # 페이지네이션
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1

    try:
        per_page = max(
            1, min(int(request.args.get("per_page", DEFAULT_PAGE_SIZE)), MAX_PAGE_SIZE)
        )
    except (TypeError, ValueError):
        per_page = DEFAULT_PAGE_SIZE

    # 쿼리 빌드
    point_wkt = f"POINT({lon} {lat})"
    point_geom = func.ST_GeomFromText(point_wkt, 4326)
    distance_expr = func.ST_Distance_Sphere(Place.coordinate, point_geom)

    query = Place.query.filter(Place.coordinate.isnot(None), distance_expr <= radius)

    # 정보 성격 필터 적용
    if sentiments:
        category_ids = []
        for sentiment in sentiments:
            cat = PlaceCategory.query.filter_by(name=sentiment).first()
            if cat:
                category_ids.append(cat.category_id)
        if category_ids:
            query = query.filter(Place.category_id.in_(category_ids))

    # 타입 필터 적용
    if type_names:
        type_ids = []
        for type_name in type_names:
            pt = PlaceType.query.filter_by(name=type_name).first()
            if pt:
                type_ids.append(pt.type_id)
        if type_ids:
            query = query.filter(Place.type_id.in_(type_ids))

    # 게시글 연동 필터 적용
    if post_filter == "with_post":
        query = query.filter(Place.linked_posts.any())
    elif post_filter == "without_post":
        query = query.filter(~Place.linked_posts.any())

    # 정렬 적용
    if sort == "recommendation_first":
        # 추천순 우선, 그 다음 최신순
        query = query.order_by(desc(Place.recommendation_score), desc(Place.created_at))
    else:  # latest_first
        # 최신순 우선, 그 다음 추천순
        query = query.order_by(desc(Place.created_at), desc(Place.recommendation_score))

    # 전체 개수 및 페이지네이션
    total = query.count()
    places = query.offset((page - 1) * per_page).limit(per_page).all()

    # 결과 직렬화 (거리 정보 포함)
    results = []
    for place in places:
        place_dict = place.to_dict()
        # 거리 계산
        place_lat = place.lat
        place_lon = place.lon
        if place_lat and place_lon:
            from apps.place.utils import haversine_m

            dist = haversine_m(lat, lon, place_lat, place_lon)
            place_dict["distance_m"] = round(dist, 1)
        else:
            place_dict["distance_m"] = None
        results.append(place_dict)

    return (
        jsonify(
            {
                "results": results,
                "meta": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "center": {"lat": lat, "lon": lon},
                    "radius": radius,
                    "filters": {
                        "sentiment": sentiments if sentiments else None,
                        "post_filter": post_filter,
                        "sort": sort,
                        "types": type_names if type_names else None,
                    },
                },
            }
        ),
        200,
    )


@bp.get("/categories")
@jwt_required(optional=True)
def get_place_categories():
    """
    Place 카테고리 목록 조회
    """
    categories = PlaceCategory.query.all()
    return (
        jsonify(
            {
                "categories": [
                    {
                        "category_id": cat.category_id,
                        "name": cat.name,
                        "description": cat.description,
                        "place_count": cat.places.count(),
                    }
                    for cat in categories
                ]
            }
        ),
        200,
    )


@bp.get("/types")
@jwt_required(optional=True)
def get_place_types():
    """
    Place 타입 목록 조회

    Query Parameters:
    - category: 카테고리 이름으로 필터 (positive/negative/neutral)
    """
    category_name = request.args.get("category", "").strip().lower()

    query = PlaceType.query

    if category_name:
        cat = PlaceCategory.query.filter_by(name=category_name).first()
        if cat:
            query = query.filter_by(category_id=cat.category_id)

    types = query.all()

    return (
        jsonify(
            {
                "types": [
                    {
                        "type_id": pt.type_id,
                        "name": pt.name,
                        "display_name": pt.display_name,
                        "icon": pt.icon,
                        "category_id": pt.category_id,
                        "category_name": pt.category.name if pt.category else None,
                        "place_count": pt.places.count(),
                    }
                    for pt in types
                ]
            }
        ),
        200,
    )


@bp.get("/stats")
@jwt_required(optional=True)
def get_place_stats():
    """
    Place 통계 조회

    Query Parameters:
    - lat: 중심 위도 (선택, 반경 통계용)
    - lon: 중심 경도 (선택, 반경 통계용)
    - radius: 반경(m, 선택)
    """
    lat_raw = request.args.get("lat")
    lon_raw = request.args.get("lon") or request.args.get("lng")
    radius_raw = request.args.get("radius")

    base_query = Place.query

    # 반경 필터 적용
    if lat_raw and lon_raw:
        lat, lat_err = _parse_float(lat_raw, "lat", -90, 90)
        lon, lon_err = _parse_float(lon_raw, "lon", -180, 180)

        if not lat_err and not lon_err:
            radius = float(radius_raw) if radius_raw else DEFAULT_POINT_RADIUS_METERS
            radius = min(radius, MAX_POINT_RADIUS_METERS)

            point_wkt = f"POINT({lon} {lat})"
            point_geom = func.ST_GeomFromText(point_wkt, 4326)
            distance_expr = func.ST_Distance_Sphere(Place.coordinate, point_geom)

            base_query = base_query.filter(
                Place.coordinate.isnot(None), distance_expr <= radius
            )

    # 전체 통계
    total_places = base_query.count()

    # 카테고리별 통계
    category_stats = []
    for cat in PlaceCategory.query.all():
        count = base_query.filter(Place.category_id == cat.category_id).count()
        category_stats.append(
            {"category_id": cat.category_id, "name": cat.name, "count": count}
        )

    # 타입별 통계
    type_stats = []
    for pt in PlaceType.query.all():
        count = base_query.filter(Place.type_id == pt.type_id).count()
        if count > 0:
            type_stats.append(
                {
                    "type_id": pt.type_id,
                    "name": pt.name,
                    "display_name": pt.display_name,
                    "count": count,
                }
            )

    # 게시글 연동 통계
    with_post = base_query.filter(Place.linked_posts.any()).count()
    without_post = base_query.filter(~Place.linked_posts.any()).count()

    # 평균 추천도/위험도
    avg_recommendation = (
        db.session.query(func.avg(Place.recommendation_score))
        .filter(Place.place_id.in_([p.place_id for p in base_query.all()]))
        .scalar()
    )

    avg_danger = (
        db.session.query(func.avg(Place.danger_level))
        .filter(Place.place_id.in_([p.place_id for p in base_query.all()]))
        .scalar()
    )

    return (
        jsonify(
            {
                "stats": {
                    "total": total_places,
                    "by_category": category_stats,
                    "by_type": type_stats,
                    "post_linked": {
                        "with_post": with_post,
                        "without_post": without_post,
                    },
                    "averages": {
                        "recommendation_score": (
                            round(float(avg_recommendation), 2)
                            if avg_recommendation
                            else None
                        ),
                        "danger_level": (
                            round(float(avg_danger), 2) if avg_danger else None
                        ),
                    },
                }
            }
        ),
        200,
    )


@bp.get("/dangerous")
@jwt_required(optional=True)
def get_dangerous_places():
    """
    위험 장소 조회 (danger_level이 높은 순)

    Query Parameters:
    - lat: 중심 위도 (선택)
    - lon: 중심 경도 (선택)
    - radius: 반경(m, 선택, 기본: 1000)
    - min_danger: 최소 위험도 (기본: 5.0)
    - page: 페이지 번호
    - per_page: 페이지당 개수
    """
    lat_raw = request.args.get("lat")
    lon_raw = request.args.get("lon") or request.args.get("lng")
    radius_raw = request.args.get("radius", "1000")
    min_danger_raw = request.args.get("min_danger", "5.0")

    min_danger, _ = _parse_float(min_danger_raw, "min_danger", 0, 10)
    if min_danger is None:
        min_danger = 5.0

    query = Place.query.filter(Place.danger_level >= min_danger)

    # 반경 필터
    if lat_raw and lon_raw:
        lat, lat_err = _parse_float(lat_raw, "lat", -90, 90)
        lon, lon_err = _parse_float(lon_raw, "lon", -180, 180)

        if not lat_err and not lon_err:
            radius = float(radius_raw) if radius_raw else 1000
            radius = min(radius, MAX_POINT_RADIUS_METERS)

            point_wkt = f"POINT({lon} {lat})"
            point_geom = func.ST_GeomFromText(point_wkt, 4326)
            distance_expr = func.ST_Distance_Sphere(Place.coordinate, point_geom)

            query = query.filter(Place.coordinate.isnot(None), distance_expr <= radius)

    # 위험도 높은 순 정렬
    query = query.order_by(desc(Place.danger_level), desc(Place.created_at))

    # 페이지네이션
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1

    try:
        per_page = max(
            1, min(int(request.args.get("per_page", DEFAULT_PAGE_SIZE)), MAX_PAGE_SIZE)
        )
    except (TypeError, ValueError):
        per_page = DEFAULT_PAGE_SIZE

    total = query.count()
    places = query.offset((page - 1) * per_page).limit(per_page).all()

    results = []
    for place in places:
        place_dict = place.to_dict()
        if lat_raw and lon_raw and place.lat and place.lon:
            from apps.place.utils import haversine_m

            dist = haversine_m(float(lat_raw), float(lon_raw), place.lat, place.lon)
            place_dict["distance_m"] = round(dist, 1)
        results.append(place_dict)

    return (
        jsonify(
            {
                "results": results,
                "meta": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "min_danger": min_danger,
                },
            }
        ),
        200,
    )


@bp.get("/recommended")
@jwt_required(optional=True)
def get_recommended_places():
    """
    추천 장소 조회 (recommendation_score가 높은 순)

    Query Parameters:
    - lat: 중심 위도 (선택)
    - lon: 중심 경도 (선택)
    - radius: 반경(m, 선택, 기본: 1000)
    - min_score: 최소 추천도 (기본: 4.0)
    - page: 페이지 번호
    - per_page: 페이지당 개수
    """
    lat_raw = request.args.get("lat")
    lon_raw = request.args.get("lon") or request.args.get("lng")
    radius_raw = request.args.get("radius", "1000")
    min_score_raw = request.args.get("min_score", "4.0")

    min_score, _ = _parse_float(min_score_raw, "min_score", 1, 5)
    if min_score is None:
        min_score = 4.0

    query = Place.query.filter(Place.recommendation_score >= min_score)

    # 반경 필터
    if lat_raw and lon_raw:
        lat, lat_err = _parse_float(lat_raw, "lat", -90, 90)
        lon, lon_err = _parse_float(lon_raw, "lon", -180, 180)

        if not lat_err and not lon_err:
            radius = float(radius_raw) if radius_raw else 1000
            radius = min(radius, MAX_POINT_RADIUS_METERS)

            point_wkt = f"POINT({lon} {lat})"
            point_geom = func.ST_GeomFromText(point_wkt, 4326)
            distance_expr = func.ST_Distance_Sphere(Place.coordinate, point_geom)

            query = query.filter(Place.coordinate.isnot(None), distance_expr <= radius)

    # 추천도 높은 순 정렬
    query = query.order_by(desc(Place.recommendation_score), desc(Place.created_at))

    # 페이지네이션
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1

    try:
        per_page = max(
            1, min(int(request.args.get("per_page", DEFAULT_PAGE_SIZE)), MAX_PAGE_SIZE)
        )
    except (TypeError, ValueError):
        per_page = DEFAULT_PAGE_SIZE

    total = query.count()
    places = query.offset((page - 1) * per_page).limit(per_page).all()

    results = []
    for place in places:
        place_dict = place.to_dict()
        if lat_raw and lon_raw and place.lat and place.lon:
            from apps.place.utils import haversine_m

            dist = haversine_m(float(lat_raw), float(lon_raw), place.lat, place.lon)
            place_dict["distance_m"] = round(dist, 1)
        results.append(place_dict)

    return (
        jsonify(
            {
                "results": results,
                "meta": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "min_score": min_score,
                },
            }
        ),
        200,
    )


# ============================================================
# 외부 API 데이터 조회 및 동기화 API
# ============================================================


@bp.get("/<int:place_id>/external")
@jwt_required(optional=True)
def get_place_external_data(place_id):
    """
    특정 장소의 외부 API(Google, Kakao) 데이터 조회

    Query Parameters:
    - source: 데이터 소스 필터 (google/kakao/all, 기본: all)
    """
    place = Place.query.get(place_id)
    if not place:
        return jsonify({"message": "Place not found"}), 404

    source = request.args.get("source", "all").strip().lower()

    result = {
        "place_id": place_id,
        "name": place.name,
        "verified": place.verified,
        "data_source": place.data_source,
    }

    if source in ("google", "all"):
        result["google"] = place._get_google_data()

    if source in ("kakao", "all"):
        result["kakao"] = place._get_kakao_data()

    return jsonify(result), 200


@bp.get("/with-google")
@jwt_required(optional=True)
def get_places_with_google_data():
    """
    Google 데이터가 있는 장소 목록 조회

    Query Parameters:
    - min_rating: 최소 Google 평점 (기본: 없음)
    - min_reviews: 최소 리뷰 수 (기본: 없음)
    - page: 페이지 번호
    - per_page: 페이지당 개수
    """
    min_rating_raw = request.args.get("min_rating")
    min_reviews_raw = request.args.get("min_reviews")

    query = Place.query.filter(Place.google_place_id.isnot(None))

    if min_rating_raw:
        min_rating, _ = _parse_float(min_rating_raw, "min_rating", 1, 5)
        if min_rating:
            query = query.filter(Place.google_rating >= min_rating)

    if min_reviews_raw:
        try:
            min_reviews = int(min_reviews_raw)
            query = query.filter(Place.google_reviews_count >= min_reviews)
        except (TypeError, ValueError):
            pass

    # Google 평점 높은 순 정렬
    query = query.order_by(desc(Place.google_rating), desc(Place.google_reviews_count))

    # 페이지네이션
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1

    try:
        per_page = max(
            1, min(int(request.args.get("per_page", DEFAULT_PAGE_SIZE)), MAX_PAGE_SIZE)
        )
    except (TypeError, ValueError):
        per_page = DEFAULT_PAGE_SIZE

    total = query.count()
    places = query.offset((page - 1) * per_page).limit(per_page).all()

    results = [place.to_dict(include_external=True) for place in places]

    return (
        jsonify(
            {
                "results": results,
                "meta": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                },
            }
        ),
        200,
    )


@bp.get("/with-kakao")
@jwt_required(optional=True)
def get_places_with_kakao_data():
    """
    Kakao 데이터가 있는 장소 목록 조회

    Query Parameters:
    - category_group: 카카오 카테고리 그룹 코드 (FD6, CE7 등)
    - page: 페이지 번호
    - per_page: 페이지당 개수
    """
    category_group = request.args.get("category_group", "").strip().upper()

    query = Place.query.filter(Place.kakao_place_id.isnot(None))

    if category_group:
        query = query.filter(Place.kakao_category_group_code == category_group)

    # 최신 동기화 순 정렬
    query = query.order_by(desc(Place.kakao_last_synced))

    # 페이지네이션
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1

    try:
        per_page = max(
            1, min(int(request.args.get("per_page", DEFAULT_PAGE_SIZE)), MAX_PAGE_SIZE)
        )
    except (TypeError, ValueError):
        per_page = DEFAULT_PAGE_SIZE

    total = query.count()
    places = query.offset((page - 1) * per_page).limit(per_page).all()

    results = [place.to_dict(include_external=True) for place in places]

    return (
        jsonify(
            {
                "results": results,
                "meta": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                },
            }
        ),
        200,
    )


@bp.get("/unsynced")
@jwt_required(optional=True)
def get_unsynced_places():
    """
    외부 API와 동기화되지 않은 장소 목록 조회

    Query Parameters:
    - source: 동기화 대상 (google/kakao/both, 기본: both)
    - days: 마지막 동기화 후 경과 일수 (기본: 없음 = 동기화된 적 없음)
    - page: 페이지 번호
    - per_page: 페이지당 개수
    """
    from datetime import datetime, timedelta

    source = request.args.get("source", "both").strip().lower()
    days_raw = request.args.get("days")

    query = Place.query

    if days_raw:
        try:
            days = int(days_raw)
            cutoff = datetime.now() - timedelta(days=days)

            if source == "google":
                query = query.filter(
                    (Place.google_last_synced.is_(None))
                    | (Place.google_last_synced < cutoff)
                )
            elif source == "kakao":
                query = query.filter(
                    (Place.kakao_last_synced.is_(None))
                    | (Place.kakao_last_synced < cutoff)
                )
            else:  # both
                query = query.filter(
                    (Place.google_last_synced.is_(None))
                    | (Place.google_last_synced < cutoff)
                    | (Place.kakao_last_synced.is_(None))
                    | (Place.kakao_last_synced < cutoff)
                )
        except (TypeError, ValueError):
            pass
    else:
        # 동기화된 적 없는 장소
        if source == "google":
            query = query.filter(Place.google_place_id.is_(None))
        elif source == "kakao":
            query = query.filter(Place.kakao_place_id.is_(None))
        else:  # both
            query = query.filter(
                Place.google_place_id.is_(None) | Place.kakao_place_id.is_(None)
            )

    # 생성일 오래된 순 (오래 된 것부터 동기화 필요)
    query = query.order_by(asc(Place.created_at))

    # 페이지네이션
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1

    try:
        per_page = max(
            1, min(int(request.args.get("per_page", DEFAULT_PAGE_SIZE)), MAX_PAGE_SIZE)
        )
    except (TypeError, ValueError):
        per_page = DEFAULT_PAGE_SIZE

    total = query.count()
    places = query.offset((page - 1) * per_page).limit(per_page).all()

    results = []
    for place in places:
        place_dict = place.to_dict()
        place_dict["sync_status"] = {
            "google_synced": place.google_place_id is not None,
            "google_last_synced": (
                place.google_last_synced.isoformat()
                if place.google_last_synced
                else None
            ),
            "kakao_synced": place.kakao_place_id is not None,
            "kakao_last_synced": (
                place.kakao_last_synced.isoformat() if place.kakao_last_synced else None
            ),
        }
        results.append(place_dict)

    return (
        jsonify(
            {
                "results": results,
                "meta": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "source": source,
                },
            }
        ),
        200,
    )


@bp.put("/<int:place_id>/sync/google")
@jwt_required()
def sync_place_google(place_id):
    """
    특정 장소의 Google Places API 데이터 수동 업데이트

    Request Body:
    - google_data: Google Places API 응답 데이터
    """
    error = admin_required()
    if error:
        return error

    place = Place.query.get(place_id)
    if not place:
        return jsonify({"message": "Place not found"}), 404

    data = request.get_json() or {}
    google_data = data.get("google_data")

    if not google_data:
        return jsonify({"message": "google_data is required"}), 400

    try:
        place.update_from_google(google_data)
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        return jsonify({"message": "Failed to sync", "error": str(exc)}), 400

    return (
        jsonify(
            {
                "message": "Google data synced",
                "place": place.to_dict(include_external=True),
            }
        ),
        200,
    )


@bp.put("/<int:place_id>/sync/kakao")
@jwt_required()
def sync_place_kakao(place_id):
    """
    특정 장소의 Kakao Local API 데이터 수동 업데이트

    Request Body:
    - kakao_data: Kakao Local API 응답 데이터
    """
    error = admin_required()
    if error:
        return error

    place = Place.query.get(place_id)
    if not place:
        return jsonify({"message": "Place not found"}), 404

    data = request.get_json() or {}
    kakao_data = data.get("kakao_data")

    if not kakao_data:
        return jsonify({"message": "kakao_data is required"}), 400

    try:
        place.update_from_kakao(kakao_data)
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        return jsonify({"message": "Failed to sync", "error": str(exc)}), 400

    return (
        jsonify(
            {
                "message": "Kakao data synced",
                "place": place.to_dict(include_external=True),
            }
        ),
        200,
    )


@bp.put("/<int:place_id>/verify")
@jwt_required()
def verify_place(place_id):
    """
    장소 정보 검증 상태 변경

    Request Body:
    - verified: true/false
    """
    error = admin_required()
    if error:
        return error

    place = Place.query.get(place_id)
    if not place:
        return jsonify({"message": "Place not found"}), 404

    data = request.get_json() or {}
    verified = data.get("verified")

    if verified is None:
        return jsonify({"message": "verified field is required"}), 400

    try:
        place.verified = bool(verified)
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        return jsonify({"message": "Failed to update", "error": str(exc)}), 400

    return (
        jsonify(
            {
                "message": "Verification status updated",
                "place_id": place_id,
                "verified": place.verified,
            }
        ),
        200,
    )


@bp.get("/external-stats")
@jwt_required(optional=True)
def get_external_sync_stats():
    """
    외부 API 동기화 통계 조회
    """
    total_places = Place.query.count()

    # Google 동기화 통계
    google_synced = Place.query.filter(Place.google_place_id.isnot(None)).count()
    google_with_rating = Place.query.filter(Place.google_rating.isnot(None)).count()
    google_avg_rating = db.session.query(func.avg(Place.google_rating)).scalar()

    # Kakao 동기화 통계
    kakao_synced = Place.query.filter(Place.kakao_place_id.isnot(None)).count()

    # Kakao 카테고리별 통계
    kakao_category_stats = (
        db.session.query(
            Place.kakao_category_group_code,
            Place.kakao_category_group_name,
            func.count(Place.place_id),
        )
        .filter(Place.kakao_category_group_code.isnot(None))
        .group_by(Place.kakao_category_group_code, Place.kakao_category_group_name)
        .all()
    )

    # 검증 통계
    verified_count = Place.query.filter(Place.verified == True).count()

    # 데이터 소스 통계
    source_stats = (
        db.session.query(Place.data_source, func.count(Place.place_id))
        .filter(Place.data_source.isnot(None))
        .group_by(Place.data_source)
        .all()
    )

    return (
        jsonify(
            {
                "stats": {
                    "total_places": total_places,
                    "google": {
                        "synced_count": google_synced,
                        "sync_rate": (
                            round(google_synced / total_places * 100, 1)
                            if total_places > 0
                            else 0
                        ),
                        "with_rating_count": google_with_rating,
                        "average_rating": (
                            round(float(google_avg_rating), 2)
                            if google_avg_rating
                            else None
                        ),
                    },
                    "kakao": {
                        "synced_count": kakao_synced,
                        "sync_rate": (
                            round(kakao_synced / total_places * 100, 1)
                            if total_places > 0
                            else 0
                        ),
                        "by_category": [
                            {
                                "code": code,
                                "name": name,
                                "count": count,
                            }
                            for code, name, count in kakao_category_stats
                        ],
                    },
                    "verification": {
                        "verified_count": verified_count,
                        "verification_rate": (
                            round(verified_count / total_places * 100, 1)
                            if total_places > 0
                            else 0
                        ),
                    },
                    "data_source": [
                        {"source": source, "count": count}
                        for source, count in source_stats
                    ],
                }
            }
        ),
        200,
    )
