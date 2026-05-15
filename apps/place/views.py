import json
import requests
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required
from sqlalchemy import cast
from sqlalchemy.exc import SQLAlchemyError
from geoalchemy2.elements import WKTElement

from apps.config.server import db
from apps.place.models import Place, func
from apps.place.utils import _build_bbox
from apps.admin.views import admin_required

bp = Blueprint("place", __name__)


@bp.get("/api_info")
def api_info():
    """Return place module API metadata for development reference.

    Returns:
        JSON response with module info and endpoint list, HTTP 200.
    """
    info = {
        "module": "place",
        "base_path": "/place",
        "description": "장소 검색 및 관리",
        "endpoints": [
            {
                "path": "/place/search",
                "method": "GET",
                "auth_required": False,
                "description": "장소 검색",
                "query_params": {
                    "q": "검색어 (필수)",
                    "lat": "중심 위도 (선택)",
                    "lon": "중심 경도 (선택)",
                    "radius": "반경(m, 기본: 500)",
                },
            },
            {
                "path": "/place/<place_id>",
                "method": "GET",
                "auth_required": False,
                "description": "특정 장소 정보 조회",
            },
            {
                "path": "/place",
                "method": "POST",
                "auth_required": True,
                "description": "장소 등록",
            },
            {
                "path": "/place/nearby",
                "method": "GET",
                "auth_required": False,
                "description": "주변 장소 조회",
            },
            {
                "path": "/place/api_info",
                "method": "GET",
                "auth_required": False,
                "description": "API 정보 조회 (개발용)",
            },
        ],
    }
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


def _fix_coords_order(coords):
    """Detect and correct swapped lat/lon order in a GeoJSON coordinate array.

    Args:
        coords: A coordinate value - either a ``[x, y]`` pair or a nested list
            of coordinate arrays.

    Returns:
        The corrected coordinate structure with ``[lon, lat]`` ordering.
    """
    if not isinstance(coords, list):
        return coords

    # Base case: [x, y]
    if len(coords) == 2 and all(isinstance(v, (int, float)) for v in coords):
        x, y = coords

        # if x is latitude (> 90 or < -90), it's wrong → swap
        if abs(x) > 90 and abs(y) <= 90:
            return [y, x]

        # if y is longitude (> 180), it's wrong → swap
        if abs(y) > 90 and abs(x) <= 90:
            return [y, x]

        # Looks normal
        return coords

    # Recursive case: nested arrays
    return [_fix_coords_order(c) for c in coords]


def _store_place_area(place, geom_obj, lat=None, lon=None):
    """Normalize a GeoJSON geometry object and assign it to a Place's ``geom`` column.

    Ensures coordinates are in ``(lon, lat)`` order and that the geometry type is
    Polygon, MultiPolygon, or LineString before calling ``ST_GeomFromGeoJSON``.

    Args:
        place: The Place ORM instance to update.
        geom_obj: A GeoJSON dict (Polygon, MultiPolygon, or LineString), or None.
        lat: Optional fallback latitude (currently unused).
        lon: Optional fallback longitude (currently unused).
    """
    if isinstance(geom_obj, dict) and geom_obj.get("type") in (
        "Polygon",
        "MultiPolygon",
        "LineString",
    ):
        try:
            geom_copy = json.loads(json.dumps(geom_obj))  # deep copy
            geom_copy["coordinates"] = _fix_coords_order(geom_copy["coordinates"])
            geojson_str = json.dumps(geom_copy)
            place.geom = func.ST_GeomFromGeoJSON(geojson_str)
        except Exception:
            place.geom = None
        return

    place.geom = None


def _lat_column():
    """Return a SQLAlchemy expression for the latitude of a Place's coordinate.

    Returns:
        A SQLAlchemy function expression equivalent to ``ST_Y(Place.coordinate)``.
    """
    return func.ST_Y(Place.coordinate)


def _lon_column():
    """Return a SQLAlchemy expression for the longitude of a Place's coordinate.

    Returns:
        A SQLAlchemy function expression equivalent to ``ST_X(Place.coordinate)``.
    """
    return func.ST_X(Place.coordinate)


def _first_segment(text):
    """Return the portion of a comma-separated string before the first comma.

    Args:
        text: Input string, potentially containing commas.

    Returns:
        The trimmed text before the first comma, or the full trimmed string if
        no comma is present.  Returns None for falsy input.
    """
        return None
    segment = text.split(",", 1)[0].strip()
    return segment or text.strip()


def _reverse_geojson_feature(data):
    """Extract the first GeoJSON Feature from a Nominatim reverse-geocode response.

    Args:
        data: The parsed JSON response dict from Nominatim, which may be a
            Feature, a FeatureCollection, or another structure.

    Returns:
        A GeoJSON Feature dict if one can be found, otherwise None.
    """
        return None
    if data.get("type") == "FeatureCollection":
        features = data.get("features") or []
        return features[0] if features else None
    if data.get("type") == "Feature":
        return data
    return None


def _bbox_to_geojson_polygon(bbox, order_hint="lonlat"):
    """Convert a bounding-box array into a GeoJSON Polygon.

    Args:
        bbox: A list or tuple of four numeric values representing the bounding box.
        order_hint: Expected coordinate order - ``"lonlat"`` (default) interprets
            the values as ``[min_lon, min_lat, max_lon, max_lat]``, while
            ``"latlon"`` interprets them as ``[min_lat, max_lat, min_lon, max_lon]``.
            If the first attempt produces an invalid polygon, the alternate order
            is tried automatically.

    Returns:
        A GeoJSON Polygon dict, or None if the bbox is invalid.
    """
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
    """Extract structured tag data from a Nominatim feature properties dict.

    Args:
        properties: A Nominatim ``properties`` dict that may contain ``address``,
            ``extratags``, ``category``, ``type``, ``addresstype``, and
            ``place_id``/``osm_id`` fields.

    Returns:
        A dict of tag data suitable for storing in ``Place.tags``.
    """
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
    """Convert a GeoJSON Feature from Nominatim into a normalised place payload dict.

    Args:
        feature: A GeoJSON Feature dict with ``geometry`` and ``properties``.

    Returns:
        A dict with ``name``, ``alt_name``, ``lat``, ``lon``, ``description``,
        and ``tags`` fields, or None if the feature is invalid.
    """
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
    """Convert a legacy (non-GeoJSON) Nominatim reverse response to a place payload dict.

    Args:
        data: A flat Nominatim reverse JSON response dict (``format=json`` style).
        fallback_lat: Latitude to use if ``data`` does not contain ``lat``.
        fallback_lon: Longitude to use if ``data`` does not contain ``lon``/``lng``.

    Returns:
        A dict with ``name``, ``alt_name``, ``lat``, ``lon``, ``description``,
        and ``tags`` fields, or None if coordinates cannot be determined.
    """
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
    """Normalise a Nominatim reverse-geocode response regardless of its format.

    Handles both GeoJSON FeatureCollection/Feature responses and legacy flat
    JSON responses, extracting geometry for the place area if available.

    Args:
        data: Parsed JSON from Nominatim reverse endpoint.
        fallback_lat: Latitude fallback when the response omits coordinates.
        fallback_lon: Longitude fallback when the response omits coordinates.

    Returns:
        A tuple of ``(payload, raw_origin, geom_obj)`` where ``payload`` is a
        normalised place dict, ``raw_origin`` is the unmodified response data,
        and ``geom_obj`` is a GeoJSON geometry dict or None.
    """
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
    """Look up a Place by name within a small geographic bounding box.

    Args:
        name: Place name to search for (case-insensitive).
        lat: Latitude of the search centre.
        lon: Longitude of the search centre.
        epsilon: Half-side of the bounding box in degrees (default 0.0005 ≈ 55 m).

    Returns:
        The most recently updated matching Place instance, or None.
    """
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
    """Parse and range-validate a numeric query parameter.

    Args:
        value: Raw string or numeric value to parse.
        field: Field name used in error messages.
        min_value: Optional inclusive lower bound.
        max_value: Optional inclusive upper bound.

    Returns:
        A tuple ``(float_value, None)`` on success, or ``(None, error_message)``
        on failure.
    """
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
    """Validate and normalise a place creation or update payload.

    Args:
        data: Dict of input fields from the request body.
        partial: If True, only fields present in ``data`` are validated (PATCH
            semantics); if False, all required fields must be present (POST semantics).

    Returns:
        A tuple ``(payload, errors)`` where ``payload`` is a dict of validated
        values and ``errors`` is a list of error message strings (empty on success).
    """

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
    """Validate a GeoJSON geometry object at a basic structural level.

    Args:
        geom: The value to validate; expected to be a dict with ``type`` and
            ``coordinates`` keys containing numeric values.

    Returns:
        None if the geometry is valid (or None), otherwise an error message string.
    """
        return None
    if not isinstance(geom, dict):
        return "geom must be a GeoJSON object"
    if "type" not in geom or "coordinates" not in geom:
        return "geom must contain type and coordinates"
    if not _coordinates_are_numeric(geom.get("coordinates")):
        return "geom coordinates must be numeric"
    return None


def _coordinates_are_numeric(coords):
    """Recursively check that all values in a GeoJSON coordinate structure are numeric.

    Args:
        coords: A number, or a (possibly nested) list of numbers.

    Returns:
        True if all leaf values are int or float, False otherwise.
    """
        return True
    if isinstance(coords, list):
        return all(_coordinates_are_numeric(c) for c in coords)
    return False


@bp.post("")
@jwt_required()
def create_place():
    """Create a new Place record (admin only).

    Expects a JSON body validated by ``_validate_place_payload``.  An optional
    ``geom`` GeoJSON field is stored via ``_store_place_area``.

    Returns:
        JSON with a confirmation message and the new place pin, HTTP 201.
        HTTP 400 if the payload is invalid or the DB write fails.
        HTTP 403 if the caller is not an admin.
    """
    if errors:
        return jsonify({"message": "Invalid input", "errors": errors}), 400

    geom_obj = payload.pop("geom", None)
    lat_val = payload.pop("lat", None)
    lon_val = payload.pop("lon", None)
    place = Place(**payload)
    place.set_lat_lon(payload["lat"], payload["lon"])

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
    """Return a paginated list of places with optional name and tag filters.

    Args (query string):
        name: Case-insensitive substring filter on the place name.
        tag: Filter to places whose tags contain this string.
        page: Page number (default 1).
        per_page: Items per page (default 20, max 100).

    Returns:
        Paginated JSON response with ``items`` list of place pin dicts, HTTP 200.
    """
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
    """Return a single place by its primary key.

    Args:
        place_id: Integer primary key of the Place.

    Returns:
        JSON with the place pin dict, HTTP 200.
        HTTP 404 if the place is not found.
    """


@bp.put("/<int:place_id>")
@jwt_required()
def update_place(place_id):
    """Update fields on an existing place (admin only).

    Applies a partial update using only fields present in the JSON body.

    Args:
        place_id: Integer primary key of the Place to update.

    Returns:
        JSON with a confirmation message and the updated place pin, HTTP 200.
        HTTP 400 if the payload is invalid or the DB write fails.
        HTTP 403 if the caller is not an admin.
        HTTP 404 if the place is not found.
    """
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
    """Delete a place by its primary key (admin only).

    Args:
        place_id: Integer primary key of the Place to delete.

    Returns:
        JSON with a confirmation message, HTTP 200.
        HTTP 400 if the DB delete fails.
        HTTP 403 if the caller is not an admin.
        HTTP 404 if the place is not found.
    """
        db.session.delete(place)
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        return jsonify({"message": "Failed to delete place", "error": str(exc)}), 400

    return jsonify({"message": "Place deleted"}), 200


def place_to_dict(place):
    """Return a frontend-friendly structure without assuming optional columns exist.

    Args:
        place: A Place ORM instance with a ``to_dict()`` method.

    Returns:
        A dict enriched with ``id``, ``display_name``, ``source``, and safe
        defaults for ``tags``, ``geom``, and ``description``.
    """
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
    """Normalise a ``Place.tags`` value to a dict or list.

    Args:
        tags: Raw tags value - may be None, a JSON string, a dict, or a list.

    Returns:
        The parsed dict or list, or an empty dict if the value is None or
        unparseable.
    """
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
    """Derive a frontend pin-type string from Nominatim category/type metadata.

    Args:
        properties: Nominatim ``properties`` dict (or any name string as fallback).
        extratags: Optional Nominatim ``extratags`` dict; read from ``properties``
            when not provided explicitly.

    Returns:
        A pin-type string such as ``"cafe"``, ``"house"``, ``"city"``, or
        ``"default"`` when no specific match is found.
    """
    if not isinstance(properties, dict):
        properties = {}
    category = (properties.get("category") or "").lower()
    ptype = (properties.get("type") or "").lower()
    addresstype = (properties.get("addresstype") or "").lower()

    if extratags is None:
        extratags = properties.get("extratags", {}) or {}

    extraclass = (extratags.get("class") or "").lower()
    extratype = (extratags.get("type") or "").lower()

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
    if (category, ptype) in CATEGORY_TYPE_MAP:
        return CATEGORY_TYPE_MAP[(category, ptype)]

    if addresstype in ("house", "building", "residential", "apartment"):
        return "house"
    if addresstype in ("city", "town", "village", "country", "state", "region"):
        return "city"

    if category == "amenity":
        return "amenity"
    if category == "shop":
        return "shopping"
    if category == "leisure":
        return "leisure"
    if category == "sport":
        return "sport"
    if category == "historic":
        return "historic"
    if category == "tourism":
        return "tourism"
    if category == "place":
        if ptype in ("city", "town", "village", "hamlet", "suburb"):
            return "city"
        return "place"

    if extraclass in ("building", "landuse"):
        return "building"

    return "default"


def _build_label(name=None, alt_name=None, display_name=None):
    """Return the best available display label from the provided name candidates.

    Args:
        name: Primary place name.
        alt_name: Alternate or display name.
        display_name: Full display name (lowest priority).

    Returns:
        The first non-empty value among ``alt_name``, ``name``, ``display_name``,
        or None if all are falsy.
    """
        if value:
            return value
    return None


def place_to_pin(place):
    """Convert a Place ORM instance to a frontend-friendly pin dict.

    Args:
        place: A Place ORM instance with a ``to_dict()`` method, or a plain dict.

    Returns:
        A dict with ``id``, ``placeId``, ``name``, ``label``, ``lat``, ``lng``,
        ``type``, ``tags``, ``source``, ``createdAt``, ``updatedAt``, and ``raw``.
    """
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
        "type": pin_type,
    }


def _resolve_coordinates(item):
    """Extract and cast lat/lon floats from a dict.

    Args:
        item: A dict expected to contain ``lat`` and ``lon`` keys.

    Returns:
        A tuple ``(lat, lon)`` as floats, or ``(None, None)`` if conversion fails.
    """
        lon = float(item.get("lon"))
        return lat, lon
    except (TypeError, ValueError):
        return None, None


def _apply_point_radius_filter(query, center, radius_meters):
    """Filter a Place SQLAlchemy query to rows within a given radius of a point.

    Args:
        query: The base SQLAlchemy query to filter.
        center: A ``(lat, lon)`` tuple for the search centre, or falsy to skip filtering.
        radius_meters: Maximum distance from the centre in metres.

    Returns:
        The filtered query (or the original query unchanged if ``center`` is falsy).
    """
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
    """Build a filtered SQLAlchemy query for Place records.

    Args:
        search_text: Optional substring to match against ``name`` and ``alt_name``
            (case-insensitive).
        tag: Optional tag substring to filter by.
        point_filter: Optional ``(lat, lon, radius_m)`` tuple for radius filtering.

    Returns:
        A SQLAlchemy Query object with the requested filters applied.
    """
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
    """Truncate a string to a maximum length.

    Args:
        value: The value to truncate; non-strings are returned unchanged.
        limit: Maximum character count (default 255).

    Returns:
        The truncated string, or the original value if it is not a string.
    """
        return value
    return value[:limit]


def _normalize_nominatim_item(item):
    """Normalise a single Nominatim search result item into a place payload dict.

    Args:
        item: A dict from the Nominatim JSON search response array.

    Returns:
        A dict with ``name``, ``alt_name``, ``lat``, ``lon``, and ``tags`` fields,
        or None if the item lacks valid coordinates or a usable name.
    """
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
    """Query the Nominatim search API and return raw result items.

    Args:
        search_text: The search query string.
        limit: Maximum number of results to request from Nominatim.

    Returns:
        A list of raw Nominatim result dicts, or an empty list on any error.
    """
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
    """Check whether a place with the given name already exists near the coordinates.

    Args:
        name: Place name to search for (case-insensitive).
        lat: Latitude of the check location.
        lon: Longitude of the check location.
        epsilon: Half-side of the bounding box in degrees (default 0.0005).

    Returns:
        True if a matching place exists within the bounding box, False otherwise.
    """
    return (
        Place.query.filter(
            func.lower(Place.name) == lowered,
            _lat_column().between(lat - epsilon, lat + epsilon),
            _lon_column().between(lon - epsilon, lon + epsilon),
        ).first()
        is not None
    )


def _ingest_nominatim_places(search_text, limit):
    """Fetch Nominatim results for a search term and persist new places to the DB.

    Skips any result that already has a matching place nearby in the database.

    Args:
        search_text: The search query string.
        limit: Maximum number of Nominatim results to process.

    Returns:
        A tuple ``(inserted, normalized, raw_items, db_error)`` where ``inserted``
        is True if at least one new place was committed, ``normalized`` is the list
        of processed payload dicts, ``raw_items`` is the unmodified Nominatim
        response list, and ``db_error`` is True if a DB commit failed.
    """
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
        place.set_lat_lon(payload["lat"], payload["lon"])

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
    """Serialize a normalised place payload dict into a frontend-compatible pin dict.

    Used for Nominatim results that have not yet been (or could not be) persisted
    to the database.

    Args:
        payload: A normalised place dict with ``name``, ``alt_name``, ``lat``,
            ``lon``, ``description``, and ``tags`` keys.

    Returns:
        A pin dict compatible with the ``place_to_pin`` output format, with
        ``id`` and ``placeId`` set to None and ``source`` set to ``"nominatim"``.
    """
    tags = None

    if isinstance(tags_raw, (dict, list)):
        # 이미 딕셔너리 또는 리스트인 경우
        tags = tags_raw
    elif isinstance(tags_raw, str):
        # 문자열인 경우, JSON 파싱을 시도합니다.
        try:
            tags = json.loads(tags_raw)
        except json.JSONDecodeError:
            # 유효하지 않은 JSON 문자열인 경우, None으로 처리하거나 로깅합니다.
            print(f"JSON Decode Error for tags: {tags_raw}")
            tags = None

    # tags가 최종적으로 딕셔너리 또는 None이 되었는지 확인합니다.

    raw = {
        "place_id": None,
        "name": payload.get("name"),
        "alt_name": payload.get("alt_name"),
        "display_name": payload.get("alt_name") or payload.get("name"),
        "description": payload.get("description"),
        "tags": tags,  # 파싱된 딕셔너리 또는 None
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
        # _derive_pin_type에 파싱된 tags 딕셔너리를 전달
        "type": _derive_pin_type(payload.get("name"), tags),
        # tags가 None일 경우 빈 딕셔너리를 사용하도록 보장
        "tags": tags or {},
        "source": "nominatim",
        "createdAt": None,
        "updatedAt": None,
        "raw": raw,
    }


@bp.get("/search")
def search_places():
    """Search for places by name, tag, and optional geographic radius.

    Falls back to Nominatim when no local results are found on the first page
    and no tag or point filter is active.

    Args (query string):
        q: Search text (optional).
        tag: Tag substring filter (optional).
        lat: Centre latitude for radius search (required if ``lon`` is provided).
        lon: Centre longitude for radius search (required if ``lat`` is provided).
        radius: Search radius in metres (default 500, max 50000).
        page: Page number (default 1).
        per_page: Items per page (default 20, max 100).

    Returns:
        JSON with ``results`` list and ``meta`` pagination dict, HTTP 200.
        HTTP 400 if lat/lon/radius values are invalid.
    """
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


@bp.get("/reverse")
def reverse_geocode():
    """Reverse-geocode a coordinate via Nominatim and persist the result.

    Always attempts to save the resolved place to the database unless a
    matching place already exists nearby.

    Args (query string):
        lat: Latitude to reverse-geocode (required).
        lon: Longitude to reverse-geocode (required).

    Returns:
        JSON with the place pin dict and a ``source`` indicator
        (``"existing"``, ``"stored"``, or ``"reverse-db-error"``), HTTP 200/201.
        HTTP 400 if coordinates are missing or out of range.
        HTTP 500 if Nominatim fails or the response cannot be normalised.
    """
    lat_raw = request.args.get("lat")
    lon_raw = request.args.get("lon")

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
