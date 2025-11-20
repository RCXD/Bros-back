# Place API

Quick reference for endpoints implemented in `apps/place/views.py` (Blueprint `place`).

## Endpoints
- `POST /place` — Create; JWT required; typically admin-only.
- `GET /place` — List; JWT optional; supports pagination and filters.
- `GET /place/<id>` — Fetch single; JWT optional.
- `PUT /place/<id>` — Update; JWT + admin check.
- `DELETE /place/<id>` — Delete; JWT + admin check.
- `GET /place/search` — Search; public in current code.

## Payloads & Params
- Required fields on create: `name`, `lat` (-90..90), `lon` (-180..180).
- Optional: `alt_name`, `description`, `tags` (array or object; string is JSON-parsed), `geom`.
- `geom` validation: GeoJSON `Polygon`, `MultiPolygon`, or `Point`; coordinates must be numeric.
- Pagination/filter query params on list: `page`, `per_page` (max 100), `name` (ilike), `tag` (contains), `bbox=min_lon,min_lat,max_lon,max_lat`.
- Search params: `q`, `bbox=lonmin,latmin,lonmax,latmax`, `tag`, `page`, `per_page`.

## Geometry rules
- Area-only persistence: only `Polygon`/`MultiPolygon` GeoJSON is stored in spatial `geom` (if column exists) or `edges` (when geom column is absent). `Point` inputs do not populate `geom`/`edges`; use `lat`/`lon` instead.
- Supplying `geom: null` clears `geom` and `edges`.
- Internal SRID 4326.

## Responses
- Create: `201 { "message": "Place created", "place": { ... } }`
- List: `200 { "items": [...], "total": N, "pages": P, "page": p, "per_page": k }`
- Get: `200 { "place": { ... } }`
- Update: `200 { "message": "Place updated", "place": { ... } }`
- Delete: `200 { "message": "Place deleted" }`
- Search: `200 { "results": [...], "meta": { "page": p, "per_page": k, "total": t } }`

### Place shape (set by `place.to_dict()` / `place_to_dict()`)
- `place_id`/`id`, `name`, `display_name`/`alt_name`, `description`, `tags`, `lat`, `lon`, `geom` (GeoJSON or null), plus metadata fields (`source`, `is_active`, `created_by`, `created_at`, `updated_at` when present).

## Curl examples
```bash
# create
curl -X POST -H "Content-Type: application/json" -H "Authorization: Bearer <TOKEN>" \
  -d '{"name":"Central Park","lat":37.5,"lon":127.0,"geom":{"type":"Polygon","coordinates":[[[127.0,37.5],[127.01,37.5],[127.01,37.6],[127.0,37.6],[127.0,37.5]]]},"tags":["park"]}' \
  https://api.example.com/place

# list with bbox
curl 'https://api.example.com/place?bbox=126.9,37.4,127.1,37.6&page=1&per_page=20'

# search
curl 'https://api.example.com/place/search?q=central&bbox=126.9,37.4,127.1,37.6'
```
