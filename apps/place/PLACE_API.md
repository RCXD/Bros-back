# Place API Specification

This document summarizes the Place API endpoints, request vectors, validation rules, and response formats based on `apps/place/views.py`.

## Endpoints

- **POST `/places`** — Create place
  - Auth: `@jwt_required()`
  - Recommended: admin-only for creation
  - Summary: Create a place with name, coordinates, optional `geom`, description, and tags. If `geom` is omitted, server builds a `POINT(lon lat)` from `lat`/`lon`.

- **GET `/places`** — List places
  - Auth: `@jwt_required(optional=True)`
  - Supports pagination, name/tag filtering, and bounding box.

- **GET `/places/<int:place_id>`** — Retrieve place
  - Auth: `@jwt_required(optional=True)`
  - Returns single place detail.

- **PUT `/places/<int:place_id>`** — Update place
  - Auth: `@jwt_required()`
  - Permission: calls `admin_required()` in current code
  - Partial or full update. `geom`, `lat`, or `lon` changes re-generate geometry or clear geometry when `geom` explicitly set to null.

- **DELETE `/places/<int:place_id>`** — Delete place
  - Auth: `@jwt_required()`
  - Permission: `admin_required()`

- **GET `/places/search`** — Search places
  - Publicly accessible in current implementation
  - Query params: `q`, `bbox`, `tag`, `page`, `per_page` and returns spatial intersection results.


## Request Vectors (Fields / Query Parameters)

### Common validation rules
- `name`: string, required for creation
- `lat`: numeric, in [-90, 90]
- `lon`: numeric, in [-180, 180]
- `geom`: GeoJSON object (optional). Must be a dict with `type` and `coordinates`, coordinates numeric.
- `tags`: JSON array or object. If provided as a string, server attempts JSON parse.
- `description`, `alt_name`: optional strings

### POST / PUT body example
```json
{
  "name": "Central Park",
  "lat": 37.5,
  "lon": 127.0,
  "geom": { "type": "Point", "coordinates": [127.0, 37.5] },
  "description": "City park",
  "tags": ["park","public"]
}
```

### GET /places query params
- `page` (int, default=1)
- `per_page` (int, default=20, max=100)
- `name` (string) — partial ilike search
- `tag` (string)
- `bbox` (string) — `min_lon,min_lat,max_lon,max_lat`

### GET /places/search params
- `q` (string) — name or display_name search
- `bbox` — `lonmin,latmin,lonmax,latmax` (spatial intersection using ST_Intersects)


## Response Formats

### Success responses
- POST `/places` (201)
```json
{ "message": "Place created", "place": { /* place.to_dict() */ } }
```

- GET `/places` (200)
```json
{
  "items": [ { /* place.to_dict() */ }, ... ],
  "total": 123,
  "pages": 7,
  "page": 1,
  "per_page": 20
}
```

- GET `/places/<id>` (200)
```json
{ "place": { /* place.to_dict() */ } }
```

- PUT `/places/<id>` (200)
```json
{ "message": "Place updated", "place": { /* updated to_dict */ } }
```

- DELETE `/places/<id>` (200)
```json
{ "message": "Place deleted" }
```

- Search (200)
```json
{
  "results": [ { /* place_to_dict */ }, ... ],
  "meta": { "page":1, "per_page":20, "total": 42 }
}
```

### Place representation (place.to_dict() / place_to_dict)
Fields returned by current code (`place_to_dict`):
- `id` or `place_id` — integer
- `name` — place name
- `display_name` / `alt_name` — optional
- `description` — text
- `tags` — array or empty list
- `geom` — GeoJSON object or `null` (ST_AsGeoJSON result parsed)
- `source` — data source (if present)
- `is_active` — boolean
- `created_by`, `created_at`, `updated_at` — metadata

Note: If `geom` is null, client can fall back to `lat`/`lon` or `edges` if provided.


## Geo / Spatial Rules
- `geom` is preferred. If omitted, server constructs `POINT(lon lat)` from `lat`/`lon` using internal `_build_geom`.
- For MySQL, WKT uses `POINT(lon lat)` (lon first). Use SRID 4326.
- `bbox` filtering can use lat/lon range or spatial intersection with `ST_MakeEnvelope`/`ST_Intersects` depending on DB.
- Returned `geom` is a GeoJSON object parsed from `ST_AsGeoJSON`.


## Errors & Status Codes
- 400 Bad Request — validation errors with `errors` array
- 404 Not Found — place not found
- 201 Created — place created
- 200 OK — successful fetch/update/delete
- DB errors return 400 with error text in `error` field


## Usage Examples (curl)
- Create:
```bash
curl -X POST -H "Content-Type: application/json" -H "Authorization: Bearer <TOKEN>" \
  -d '{"name":"중앙공원","lat":37.5,"lon":127.0,"description":"도심 공원"}' \
  https://api.example.com/places
```

- List with bbox:
```bash
curl 'https://api.example.com/places?bbox=126.9,37.4,127.1,37.6&page=1&per_page=20'
```

- Search:
```bash
curl 'https://api.example.com/places/search?q=중앙공원&bbox=126.9,37.4,127.1,37.6'
```


## Recommendations / Notes
- Enforce admin-only creation/modification for place data.
- Document `Place` schema and add Alembic migration for `geom` and SPATIAL index.
- For large-scale geo queries, test `SPATIAL` index performance and create appropriate indexes for `lat`/`lon`.
- Prefer returning GeoJSON for `geom` so frontend can render geometries directly.


---

Generated from `apps/place/views.py` implementation. If you want this converted to OpenAPI/Swagger or a sample JSON response file, tell me which format and I will create the file.