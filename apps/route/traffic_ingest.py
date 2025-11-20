from datetime import datetime, timedelta

import requests
from apps.config.server import db
from apps.route.hazard_pipeline import schedule_osrm_customize
from apps.route.models import KSLink, TrafficHazard

__all__ = [
    "fetch_utic_feed",
    "parse_utic_payload",
    "traffic_penalty",
    "ingest_utic_item",
    "ingest_utic_items",
    "cleanup_stale_traffic",
]


def fetch_utic_feed(api_url, api_key=None, params=None, timeout=2.0):
    """Pull a UTIC feed from the API and normalize to a list of items."""
    headers = {}
    if api_key:
        headers["x-api-key"] = api_key
    resp = requests.get(api_url, headers=headers, params=params, timeout=timeout)
    resp.raise_for_status()
    payload = resp.json()
    if isinstance(payload, dict):
        return payload.get("items") or payload.get("data") or []
    if isinstance(payload, list):
        return payload
    return []


def parse_utic_payload(item):
    """Normalize a UTIC feed item into the attributes we care about."""
    return {
        "link_id": item.get("linkId") or item.get("link_id"),
        "speed": float(item.get("speed", 0)),
        "traffic": item.get("traffic"),
        "travel_time": float(item.get("travelTime") or item.get("travel_time") or 0),
    }


def traffic_penalty(speed):
    """Convert a reported speed into a routing penalty multiplier."""
    if speed > 40:
        return 1.0
    if speed > 20:
        return 1.2
    if speed > 10:
        return 1.5
    if speed > 0:
        return 2.0
    return 3.0


def ingest_utic_item(item):
    """Persist the hazard data from a UTIC item to all related edges."""
    data = parse_utic_payload(item)
    link_id = data.get("link_id")
    if not link_id:
        return False
    kslink = KSLink.query.get(link_id)
    if not kslink or not kslink.osm_edges:
        return False
    penalty = traffic_penalty(data["speed"])
    for edge in kslink.osm_edges:
        row = TrafficHazard.query.filter_by(osm_edge_id=edge).first()
        if not row:
            row = TrafficHazard(
                link_id=link_id,
                osm_edge_id=edge,
                penalty=penalty,
            )
            db.session.add(row)
        else:
            row.penalty = penalty
    db.session.commit()
    schedule_osrm_customize()
    return True


def ingest_utic_items(items):
    """Run `ingest_utic_item` over a sequence and track successes/skip counts."""
    summary = {"ingested": 0, "skipped": 0}
    for item in items:
        if ingest_utic_item(item):
            summary["ingested"] += 1
        else:
            summary["skipped"] += 1
    return summary


def cleanup_stale_traffic(minutes=5):
    """Remove traffic hazards that have not been updated within `minutes`."""
    cutoff = datetime.now() - timedelta(minutes=minutes)
    TrafficHazard.query.filter(TrafficHazard.updated_at < cutoff).delete()
    db.session.commit()
