import json
import requests
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required
from sqlalchemy import cast
from sqlalchemy.exc import SQLAlchemyError

from apps.config.server import db
from apps.place.models import Place, func
from apps.place.utils import _build_bbox
from apps.admin.views import admin_required

bp = Blueprint("place", __name__)

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
            place.geom = _build_bbox(lat_val, lon_val)
        if has_edges_column:
            place.edges = None
        return

    if has_geom_column:
        geom_value = _build_bbox(lat_val, lon_val, geom_obj)
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
        "type": _derive_pin_type(payload.get("name"), tags),
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
