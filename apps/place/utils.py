from math import radians, sin, cos, asin, sqrt
import re
import json
import time
from functools import wraps
from flask import jsonify, g, request
# from rapidfuzz import fuzz, distance
from sqlalchemy import func, text

from apps.config.server import db
from apps.place.models import Place

# haversine distance in meters
def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return R * c

_SUFFIX_CACHE = {"list": None, "ts": 0}
_SUFFIX_CACHE_TTL = 300  # seconds

def get_common_suffixes(force: bool = False):
    """Load common suffixes from DB table `place_name_suffixes` if available.
    Expected table schema (simple):
      CREATE TABLE place_name_suffixes (suffix VARCHAR(128) PRIMARY KEY, active BOOLEAN DEFAULT 1);
    If table doesn't exist or query fails, fall back to built-in list.
    Results are cached for `_SUFFIX_CACHE_TTL` seconds.
    """
    now = time.time()
    if not force and _SUFFIX_CACHE.get("list") and now - _SUFFIX_CACHE.get("ts", 0) < _SUFFIX_CACHE_TTL:
        return _SUFFIX_CACHE["list"]

    # derive suffixes from existing Place.name values
    try:
        res = db.session.execute(text("SELECT name FROM place WHERE name IS NOT NULL"))
        names = [r[0] for r in res if r[0]]
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        names = []

    if not names:
        builtin = ["카페", "커피", "편의점", "식당", "레스토랑", "역", "지점", "매장", "점", "샵", "숍", "센터", "마트"]
        _SUFFIX_CACHE["list"] = builtin
        _SUFFIX_CACHE["ts"] = now
        return builtin

    # count suffix occurrences (1..4 chars) from normalized names
    counts = {}
    for raw in names:
        n = normalize_ko(raw)
        if not n:
            continue
        # consider tokens (split by space) and also whole name
        tokens = n.split()
        for tok in tokens:
            L = len(tok)
            for l in range(1, min(4, L) + 1):
                suf = tok[-l:]
                if not suf:
                    continue
                counts[suf] = counts.get(suf, 0) + 1

    # choose suffixes with reasonable frequency
    total_names = len(names)
    min_count = max(3, int(total_names * 0.01))  # at least 1% or 3 occurrences
    # sort by frequency desc and length desc (prefer longer meaningful suffixes)
    cand = sorted([(s, c) for s, c in counts.items() if c >= min_count], key=lambda x: (x[1], len(x[0])), reverse=True)
    result = [s for s, _ in cand][:30]
    if not result:
        # fallback
        result = ["카페", "커피", "편의점", "식당", "레스토랑", "역", "지점", "매장", "점", "샵", "숍", "센터", "마트"]

    _SUFFIX_CACHE["list"] = result
    _SUFFIX_CACHE["ts"] = now
    return result


def normalize_ko(s: str) -> str:
    if not s:
        return ""
    s = s.strip()
    s = re.sub(r"[〈〉\[\]\(\)\{\}\/\\\|@#\$%\^&\*~`\"'.,!?;:+=—–·…·]", " ", s)
    s = re.sub(r"\s+", " ", s)
    COMMON_SUFFIXES = get_common_suffixes()
    for suf in COMMON_SUFFIXES:
        s = re.sub(rf"\b{suf}\b$", "", s)
        s = re.sub(rf"\b{suf}\b", "", s)
    s = s.strip()
    return s

def char_bigrams(s: str):
    s = f"#{s}#"
    return [s[i:i+2] for i in range(len(s)-1)]

def dice_coef_bigrams(a: str, b: str):
    A = char_bigrams(a)
    B = char_bigrams(b)
    if not A or not B:
        return 0.0
    setA = {}
    for x in A:
        setA[x] = setA.get(x, 0) + 1
    setB = {}
    for x in B:
        setB[x] = setB.get(x, 0) + 1
    inter = 0
    for k, v in setA.items():
        inter += min(v, setB.get(k, 0))
    dice = (2.0 * inter) / (len(A) + len(B))
    return dice

# def name_similarity_ko(a: str, b: str) -> float:
#     a_n = normalize_ko(a)
#     b_n = normalize_ko(b)
#     if not a_n or not b_n:
#         return 0.0
#     jw = distance.JaroWinkler.similarity(a_n, b_n) / 100.0
#     bigram = dice_coef_bigrams(a_n, b_n)
#     token = fuzz.token_set_ratio(a_n, b_n) / 100.0
#     score = 0.5 * bigram + 0.3 * jw + 0.2 * token
#     return score

def dynamic_name_threshold_ko(name: str, base=0.82) -> float:
    n = normalize_ko(name)
    if not n:
        return base
    length = len(n.replace(" ", ""))
    if length <= 2:
        return min(0.99, base + 0.15)
    if length <= 4:
        return min(0.95, base + 0.08)
    if length <= 8:
        return base
    return max(0.65, base - 0.08)

def is_name_similar_ko(a, b, lat_a=None, lon_a=None, lat_b=None, lon_b=None, base_threshold=0.82):
    # score = name_similarity_ko(a, b)
    thr_a = dynamic_name_threshold_ko(a, base=base_threshold)
    thr_b = dynamic_name_threshold_ko(b, base=base_threshold)
    threshold = max(thr_a, thr_b)
    if None not in (lat_a, lon_a, lat_b, lon_b):
        d = haversine_m(lat_a, lon_a, lat_b, lon_b)
        if d <= 20:
            threshold = max(0.45, threshold - 0.20)
        elif d <= 50:
            threshold = max(0.55, threshold - 0.10)
            
    return (False, 0.0, threshold)
    # return (score >= threshold, score, threshold)


def _build_geom(lat, lon, geojson_obj=None):
    """Build a geometry value using GeoJSON when provided, otherwise POINT(lon lat)."""
    if geojson_obj:
        try:
            payload = json.dumps(geojson_obj)
            return func.ST_SRID(func.ST_GeomFromGeoJSON(payload), 4326)
        except Exception:
            pass
    if lat is None or lon is None:
        return None
    wkt_point = f"POINT({lon} {lat})"
    return func.ST_SRID(func.ST_GeomFromText(wkt_point), 4326)


def _nearby_candidates(lat, lon, radius_m=50, limit=10):
    # Try to use MySQL ST_Distance_Sphere if geom exists, otherwise fallback to lat/lon box.
    sql = """
    SELECT place_id, name, lat, lon,
      ST_Distance_Sphere(geom, ST_GeomFromText(:point, 4326)) AS dist
    FROM place
    WHERE geom IS NOT NULL
      AND ST_Distance_Sphere(geom, ST_GeomFromText(:point,4326)) <= :radius
    ORDER BY dist ASC
    LIMIT :limit
    """
    point_wkt = f"POINT({lon} {lat})"
    try:
        res = db.session.execute(text(sql), {"point": point_wkt, "radius": radius_m, "limit": limit})
        rows = [dict(r) for r in res]
        if rows:
            return rows
    except Exception:
        # DB may not support ST_Distance_Sphere or geom is not populated; fallback below
        db.session.rollback()

    # fallback: bounding box filter (approx). convert radius to degrees ~ radius/111000
    delta = radius_m / 111000.0
    q = Place.query.filter(
        Place.lat.between(lat - delta, lat + delta),
        Place.lon.between(lon - delta, lon + delta)
    ).limit(limit)
    return [ {"place_id": p.place_id, "name": p.name, "lat": p.lat, "lon": p.lon, "dist": haversine_m(lat, lon, p.lat, p.lon)} for p in q ]

def find_similar(lat, lon, name, distance_threshold_m=50, name_threshold=0.75, limit=10):
    candidates = _nearby_candidates(lat, lon, distance_threshold_m, limit)
    results = []
    for c in candidates:
        dist = c.get("dist") or haversine_m(lat, lon, c["lat"], c["lon"])
        is_sim, score, used_thr = is_name_similar_ko(
            name, c.get("name") or "", lat, lon, c.get("lat"), c.get("lon"), base_threshold=name_threshold
        )
        if dist <= distance_threshold_m and is_sim:
            results.append({"place_id": c["place_id"], "dist": dist, "name_sim": score, "threshold": used_thr})
    return results

def create_or_get_similar(payload: dict, distance_threshold_m=50, name_threshold=0.75, commit=True):
    name = payload.get("name", "").strip()
    lat = float(payload.get("lat"))
    lon = float(payload.get("lon"))
    # find similar
    sims = find_similar(lat, lon, name, distance_threshold_m=distance_threshold_m, name_threshold=name_threshold)
    if sims:
        # pick best candidate (lowest dist, highest name_sim)
        sims.sort(key=lambda x: (x["dist"], -x["name_sim"]))
        existing = Place.query.get(sims[0]["place_id"])
        return existing, False  # False == not created

    # create new
    place = Place(
        name=name,
        alt_name=payload.get("alt_name"),
        lat=lat,
        lon=lon,
        description=payload.get("description"),
        tags=payload.get("tags"),
        geom=_build_geom(lat, lon, payload.get("geom")),
    )
    db.session.add(place)
    if commit:
        db.session.commit()
    return place, True  # True == created

def validate_place_exists(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        pid = kwargs.get("place_id") or request.json.get("place_id") if request.is_json else None
        if not pid:
            return jsonify({"message": "place_id required"}), 400
        place = Place.query.get(pid)
        if not place:
            return jsonify({"message": "Place not found"}), 404
        g.place = place
        return f(*args, **kwargs)
    return decorated
