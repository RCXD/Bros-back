import csv
from typing import Iterable
import os

import requests
from apps.config.server import db
from apps.route.models import KSLink

_INTERPOLATE_STEPS = 12


def _match_osm_edge(lat, lon, session, base_url=None, profile=None):
    """Request the nearest OSRM edge for a given lat/lon and return its identifier.

    Args:
        lat: Latitude of the probe point.
        lon: Longitude of the probe point.
        session: Requests session used for HTTP calls.
        base_url: Optional override for the OSRM server URL.
        profile: Optional override for the OSRM routing profile.

    Returns:
        Edge identifier string (prefixed with ``osm:`` or ``osrm:``) on success, ``None`` if the
        request fails or no edge data is available.
    """
    base = (base_url or os.getenv("OSRM_BASE_URL") or "http://localhost:8000").rstrip(
        "/"
    )
    prof = profile or os.getenv("OSRM_PROFILE") or "driving"
    url = f"{base}/nearest/v1/{prof}/{lon},{lat}?number=1"
    try:
        resp = session.get(url, timeout=1.5)
        if resp.status_code != 200:
            return None
        payload = resp.json()
    except Exception:
        return None

    waypoints = payload.get("waypoints") or []
    if not waypoints:
        return None
    nodes = waypoints[0].get("nodes") or []
    if len(nodes) >= 2:
        a, b = sorted(nodes[:2])
        return f"osm:{a}-{b}"
    location = waypoints[0].get("location") or []
    if len(location) == 2:
        return f"osrm:{location[1]:.5f}:{location[0]:.5f}"
    return None


def _segment_edges(p1, p2, session, base_url=None, profile=None):
    """Interpolate along a KSLink segment and aggregate nearby OSM edges.

    Args:
        p1: Point dictionary with ``lat``/``lon`` for the segment start.
        p2: Point dictionary for the segment end.
        session: Requests session shared across lookups.
        base_url: Optional OSRM host override.
        profile: Optional OSRM profile override.

    Returns:
        Set of unique edge identifiers collected along the interpolated segment.
    """
    edges = set()
    for step in range(_INTERPOLATE_STEPS + 1):
        t = step / _INTERPOLATE_STEPS
        lat = p1["lat"] + (p2["lat"] - p1["lat"]) * t
        lon = p1["lon"] + (p2["lon"] - p1["lon"]) * t
        edge = _match_osm_edge(lat, lon, session, base_url=base_url, profile=profile)
        if edge:
            edges.add(edge)
    return edges


def _to_point(coord):
    """Convert a coordinate tuple/list into a latitude/longitude dict."""
    if not coord or len(coord) < 2:
        return None
    return {"lat": float(coord[1]), "lon": float(coord[0])}


def _ensure_points(geom):
    """Return a list of latitude/longitude dictionaries from geometry coordinates."""
    points = []
    if not isinstance(geom, Iterable):
        return points
    for coord in geom:
        pt = _to_point(coord)
        if pt:
            points.append(pt)
    return points


def map_kslink_to_osm_edges(kslink, base_url=None, profile=None, session=None):
    """Map a KSLink geometry to the OSRM/OSM edge identifiers covering the path.

    Args:
        kslink: KSLink instance to map.
        base_url: Optional OSRM host override.
        profile: Optional OSRM profile override.
        session: Optional requests session, reused for multiple lookups.

    Returns:
        Sorted list of unique edge identifiers that cover the KSLink geometry.
    """
    if not kslink.geom:
        return []
    points = _ensure_points(kslink.geom)
    if len(points) < 2:
        return []
    http = session or requests.Session()
    edges = set()
    for idx in range(len(points) - 1):
        edges.update(
            _segment_edges(
                points[idx],
                points[idx + 1],
                session=http,
                base_url=base_url,
                profile=profile,
            )
        )
    return sorted(edges)


def map_all_kslinks(limit=None, base_url=None, profile=None):
    """Populate ``KSLink.osm_edges`` for all unmapped links via OSRM lookups.

    Args:
        limit: Optional cap on the number of records to process.
        base_url: Optional override for the OSRM server.
        profile: Optional override for the OSRM profile.

    Returns:
        Mapping statistics containing ``processed`` and ``mapped`` counts.
    """
    query = KSLink.query.order_by(KSLink.link_id.asc())
    if limit:
        query = query.limit(int(limit))
    session = requests.Session()
    processed = 0
    updated = 0
    for kslink in query:
        processed += 1
        if kslink.osm_edges:
            continue
        edges = map_kslink_to_osm_edges(
            kslink, base_url=base_url, profile=profile, session=session
        )
        if not edges:
            continue
        kslink.osm_edges = edges
        db.session.add(kslink)
        updated += 1
    if updated:
        db.session.commit()
    return {"processed": processed, "mapped": updated}


def _parse_linestring(text):
    """Parse WKT LINESTRING or MULTILINESTRING text into coordinate pairs.

    Args:
        text: WKT representation of a line or multilinestring.

    Returns:
        List of [lon, lat] pairs extracted from the text, or an empty list for invalid input.
    """
    if not text:
        return []
    text = text.strip()
    if text.upper().startswith("LINESTRING"):
        coords = text[text.find("(") + 1 : text.rfind(")")]
        return [[float(c.split()[0]), float(c.split()[1])] for c in coords.split(",") if c.strip()]
    if text.upper().startswith("MULTILINESTRING"):
        body = text[text.find("((") + 2 : text.rfind("))")]
        result = []
        for segment in body.split("),("):
            for pair in segment.split(","):
                pair = pair.strip()
                if not pair:
                    continue
                values = pair.split()
                if len(values) < 2:
                    continue
                result.append([float(values[0]), float(values[1])])
        return result
    return []


def load_kslinks_from_csv(path, limit=None):
    """Import KSLink definitions from CSV and update the database accordingly.

    Args:
        path: Filesystem path to the CSV file.
        limit: Optional cap on the number of rows to ingest.

    Returns:
        Counts for rows ``created``, ``updated``, and ``skipped``.
    """
    created = 0
    updated = 0
    skipped = 0
    key_map = {
        "link": ["LINK_ID", "link_id", "id"],
        "f_node": ["F_NODE", "f_node"],
        "t_node": ["T_NODE", "t_node"],
        "geom": ["geometry", "geom", "wkt"],
    }
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if limit and created + updated >= limit:
                break
            link_id = next((row.get(k) for k in key_map["link"] if row.get(k)), None)
            if not link_id:
                skipped += 1
                continue
            f_node = next((row.get(k) for k in key_map["f_node"] if row.get(k)), None)
            t_node = next((row.get(k) for k in key_map["t_node"] if row.get(k)), None)
            geom_text = next((row.get(k) for k in key_map["geom"] if row.get(k)), None)
            geom = _parse_linestring(geom_text)
            if len(geom) < 2:
                skipped += 1
                continue
            existing = KSLink.query.get(link_id)
            if existing:
                existing.f_node = f_node
                existing.t_node = t_node
                existing.geom = geom
                updated += 1
            else:
                kslink = KSLink(link_id=link_id, f_node=f_node, t_node=t_node, geom=geom)
                db.session.add(kslink)
                created += 1
    if created or updated:
        db.session.commit()
    return {"created": created, "updated": updated, "skipped": skipped}
