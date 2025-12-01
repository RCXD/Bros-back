"""Utility helpers for generating map-based post thumbnails."""

from __future__ import annotations

import json
from io import BytesIO
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from uuid import uuid4

import requests
from flask import current_app

from apps.common.image_handlers import delete_image, save_to_disk
from apps.config.server import db
from apps.image.models import Image

DEFAULT_MAP_SIZE = (600, 400)
DEFAULT_SINGLE_POINT_ZOOM = 15
MIN_PADDING_DEGREES = 0.005
THUMBNAIL_CATEGORY = "post_thumbnail"
THUMBNAIL_IMAGE_TYPE = "thumbnail"


class ThumbnailGenerationError(RuntimeError):
    """Raised when a map thumbnail cannot be created."""


def normalize_location_points(
    raw_points: Optional[Any] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> List[Dict[str, float]]:
    """Normalize arbitrary location payloads into a list of {lat, lon} dicts."""

    parsed: List[Dict[str, float]] = []
    payload = raw_points

    if isinstance(payload, str):
        stripped = payload.strip()
        if stripped:
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                parts = [part.strip() for part in stripped.split(",")]
                if len(parts) >= 2:
                    try:
                        payload = [float(parts[0]), float(parts[1])]
                    except (TypeError, ValueError):
                        payload = None
                else:
                    payload = None
        else:
            payload = None

    if isinstance(payload, dict):
        payload = [payload]

    candidate: Sequence[Any] = []
    if isinstance(payload, (list, tuple)):
        candidate = payload
        if (
            candidate
            and isinstance(candidate[0], (int, float, str))
            and not isinstance(candidate[0], (list, tuple, dict))
        ):
            candidate = [candidate]

    for item in candidate:
        if isinstance(item, dict):
            lat = item.get("lat") or item.get("latitude")
            lon = item.get("lon") or item.get("longitude")
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            lat, lon = item[0], item[1]
        else:
            continue

        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except (TypeError, ValueError):
            continue
        parsed.append({"lat": lat_f, "lon": lon_f})

    if not parsed and latitude is not None and longitude is not None:
        try:
            parsed.append({"lat": float(latitude), "lon": float(longitude)})
        except (TypeError, ValueError):
            pass

    return parsed


def generate_post_thumbnail(
    post,
    points: Optional[Iterable[Dict[str, float]]] = None,
    provider: str = "openstreet",
    location_name: Optional[str] = None,
):
    """Generate (or refresh) a thumbnail image for the given post."""

    normalized = normalize_location_points(points)
    if not normalized:
        raise ThumbnailGenerationError("No valid coordinates supplied")

    image_bytes = _fetch_map_image(normalized, provider, location_name)
    if not image_bytes:
        raise ThumbnailGenerationError("Thumbnail API returned empty payload")

    return _persist_thumbnail(post, image_bytes)


def remove_post_thumbnail(post) -> bool:
    """Remove the current thumbnail image from a post (file + DB record)."""

    if not post.thumbnail_id:
        return False

    image = db.session.get(Image, post.thumbnail_id)
    post.thumbnail_id = None

    if not image:
        return False

    delete_image(image, category=THUMBNAIL_CATEGORY)
    db.session.delete(image)
    return True


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _fetch_map_image(
    points: List[Dict[str, float]],
    provider: str,
    location_name: Optional[str] = None,
    size: Tuple[int, int] = DEFAULT_MAP_SIZE,
) -> bytes:
    provider = (provider or "openstreet").lower()

    if provider == "openstreet":
        base_url, params, headers = _build_openstreet_request(points, size)
    elif provider == "kakao":
        # TODO: Kakao Static Map 지원 (향후 활성화)
        # kakao_base = "https://dapi.kakao.com/v2/maps/static"
        # kakao_headers = {"Authorization": f"KakaoAK {current_app.config.get('KAKAO_REST_API_KEY')}"}
        # kakao_params = {"w": size[0], "h": size[1], ...}
        raise ThumbnailGenerationError("Kakao map provider is not enabled yet")
    elif provider == "google":
        # TODO: Google Static Map 지원 (API 키 필요)
        # google_base = "https://maps.googleapis.com/maps/api/staticmap"
        # google_params = {"size": f"{size[0]}x{size[1]}", "path": ..., "key": current_app.config.get("GOOGLE_MAPS_API_KEY")}
        raise ThumbnailGenerationError("Google map provider is not enabled yet")
    else:
        raise ThumbnailGenerationError(f"Unsupported thumbnail provider: {provider}")

    headers = {"User-Agent": "BrosThumbnailBot/1.0", **headers}

    try:
        # Build full URL manually - OpenStreetMap staticmap needs raw params
        # Cannot use requests params dict as it encodes ,|: chars causing 400 errors
        query_parts = []
        for key, value in params.items():
            query_parts.append(f"{key}={value}")
        query_string = "&".join(query_parts)
        full_url = f"{base_url}?{query_string}"

        response = requests.get(full_url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.content
    except requests.RequestException as exc:
        raise ThumbnailGenerationError(str(exc)) from exc


def _build_openstreet_request(
    points: List[Dict[str, float]], size: Tuple[int, int]
) -> Tuple[str, Dict[str, str], Dict[str, str]]:
    base_url = (
        current_app.config.get("OPENSTREET_STATIC_ENDPOINT")
        or current_app.config.get("OPENSTREET_URL")
        or "https://staticmap.openstreetmap.de/staticmap.php"
    ).rstrip("?")

    if "staticmap" not in base_url:
        base_url = f"{base_url.rstrip('/')}/staticmap.php"

    params: Dict[str, str] = {
        "size": f"{size[0]}x{size[1]}",
        "format": "png",
    }

    if len(points) == 1:
        lat = points[0]["lat"]
        lon = points[0]["lon"]
        params["center"] = f"{lon:.6f},{lat:.6f}"
        params["zoom"] = str(DEFAULT_SINGLE_POINT_ZOOM)
    else:
        # Calculate center and zoom for multiple points
        lats = [p["lat"] for p in points]
        lons = [p["lon"] for p in points]
        center_lat = (min(lats) + max(lats)) / 2
        center_lon = (min(lons) + max(lons)) / 2
        params["center"] = f"{center_lon:.6f},{center_lat:.6f}"

        # Calculate appropriate zoom level based on span
        lat_span = max(lats) - min(lats)
        lon_span = max(lons) - min(lons)
        max_span = max(lat_span, lon_span)

        # Rough zoom calculation (adjust as needed)
        if max_span > 0.5:
            zoom = 10
        elif max_span > 0.1:
            zoom = 12
        elif max_span > 0.05:
            zoom = 13
        elif max_span > 0.01:
            zoom = 14
        else:
            zoom = 15
        params["zoom"] = str(zoom)
        params["path"] = _encode_path(points)

    params["markers"] = _encode_markers(points)
    return base_url, params, {}


def _expand_bbox(points: List[Dict[str, float]], padding_ratio: float = 0.15):
    lats = [p["lat"] for p in points]
    lons = [p["lon"] for p in points]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    lat_span = max_lat - min_lat
    lon_span = max_lon - min_lon

    lat_padding = max(lat_span * padding_ratio, MIN_PADDING_DEGREES)
    lon_padding = max(lon_span * padding_ratio, MIN_PADDING_DEGREES)

    return {
        "min_lat": min_lat - lat_padding,
        "max_lat": max_lat + lat_padding,
        "min_lon": min_lon - lon_padding,
        "max_lon": max_lon + lon_padding,
    }


def _encode_markers(points: List[Dict[str, float]]) -> str:
    if not points:
        return ""

    markers = []
    for idx, point in enumerate(points):
        color = "lightblue1"
        if idx == 0:
            color = "green"
        elif idx == len(points) - 1:
            color = "red"
        markers.append(f"{point['lon']:.6f},{point['lat']:.6f},{color}")
    return "|".join(markers)


def _encode_path(points: List[Dict[str, float]]) -> str:
    coord_chain = "|".join(f"{p['lon']:.6f},{p['lat']:.6f}" for p in points)
    return f"color:0x0066ffff|weight:4|{coord_chain}"


def _persist_thumbnail(post, image_bytes: bytes):
    buffer = BytesIO(image_bytes)
    buffer.seek(0)
    filename = f"thumbnail_{post.post_id}_{uuid4().hex[:8]}.png"

    rel_path = save_to_disk(buffer, "png", filename, category=THUMBNAIL_CATEGORY)

    image = Image(
        post_id=post.post_id,
        user_id=post.user_id,
        directory=rel_path,
        original_image_name=filename,
        ext="png",
        image_type=THUMBNAIL_IMAGE_TYPE,
    )
    db.session.add(image)
    db.session.flush()

    previous_id = post.thumbnail_id
    post.thumbnail_id = image.image_id

    if previous_id and previous_id != image.image_id:
        old_image = db.session.get(Image, previous_id)
        if old_image:
            delete_image(old_image, category=THUMBNAIL_CATEGORY)
            db.session.delete(old_image)

    return image
