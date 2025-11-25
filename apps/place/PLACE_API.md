# Place API Reference

The Place blueprint (`apps/place/views.py`) is mounted under `/places`. Responses are JSON and represent either saved pins or transient search results. Unless otherwise noted, errors return a 400 with `{ "message": "...", "errors": [...] }`.

## Endpoint Summary
| Method | Path | Auth | Role Requirement | Description |
| ------ | ---- | ---- | ---------------- | ----------- |
| POST | `/places` | `jwt_required()` | `admin_required()` | Create a place using explicit coordinates and optional geometry/tags. |
| GET | `/places` | `jwt_required(optional=True)` | Any | Paginated list with optional name and tag filters. |
| GET | `/places/<place_id>` | `jwt_required(optional=True)` | Any | Fetch a single place. |
| PUT | `/places/<place_id>` | `jwt_required()` | `admin_required()` | Partial update; supports geometry replacement/clear. |
| DELETE | `/places/<place_id>` | `jwt_required()` | `admin_required()` | Remove a place. |
| GET | `/places/search` | Public | Any | Text / tag / radius search with Nominatim fallback. |

## Common Request Rules
- Coordinate validation: `lat` must be between -90 and 90, `lon` between -180 and 180. Values are parsed via `_parse_float`.
- `geom` must be a GeoJSON object containing `type` and numeric `coordinates`. When omitted, the server builds a point geometry from `lat`/`lon`.
- `tags` may be sent as JSON, a Python object, or a JSON string; only dicts/arrays survive validation.
- `name` is mandatory on create and optional on update. `alt_name`, `description`, and `geom` are optional everywhere.
- Pagination accepts `page` (>=1) and `per_page` (1‒100). Defaults come from `DEFAULT_PAGE_SIZE` (20).

### Request Body Shape (POST / PUT)
```json
{
  "name": "Central Park",
  "lat": 37.5,
  "lon": 127.0,
  "alt_name": "NYC Central Park",
  "description": "City park",
  "tags": {"category": "park", "district": "Manhattan"},
  "geom": { "type": "Point", "coordinates": [127.0, 37.5] }
}
```

## Endpoint Details

### POST `/places`
- Requires a valid JWT and `admin_required()`.
- Validates payload via `_validate_place_payload`; rejects missing name/lat/lon, malformed tags, or invalid GeoJSON.
- `_set_place_coordinate` writes the 4326 point to `Place.coordinate`. `_store_place_area` prefers the spatial `geom` column when available and falls back to an `edges` JSON column.
- Response `201`:
```json
{
  "message": "Place created",
  "pin": { /* pin object, see below */ }
}
```

### GET `/places`
- Optional JWT; unauthenticated users can read.
- Query params:
  - `page`, `per_page`
  - `name` – case-insensitive substring match against `Place.name`.
  - `tag` – passed to `Place.tags.contains`; use exact key/value substrings for best results.
- Returns latest entries first (`created_at desc`).
- Response `200`:
```json
{
  "items": [ { /* pin */ }, ... ],
  "total": 125,
  "pages": 7,
  "page": 1,
  "per_page": 20
}
```

### GET `/places/<place_id>`
- Optional JWT.
- Returns `404 {"message": "Place not found"}` when absent.
- Success payload:
```json
{ "place": { /* pin */ } }
```

### PUT `/places/<place_id>`
- Requires admin JWT.
- Allows partial updates. Any field supplied is validated like POST.
- Sending `"geom": null` clears both `geom` and `edges` (if the model exposes them). Updating `lat`/`lon` regenerates the stored geometry.
- Response `200 {"message": "Place updated", "pin": { ... } }`.

### DELETE `/places/<place_id>`
- Requires admin JWT.
- On success: `200 {"message": "Place deleted"}`.

### GET `/places/search`
- Public endpoint intended for fast UI searches.
- Query params:
  - `q` – case-insensitive substring search across `name` and `alt_name`.
  - `tag` – case-insensitive substring match over serialized `Place.tags`.
  - `lat` & (`lon` or `lng`) with optional `radius` – activates `_apply_point_radius_filter` which uses `ST_Distance_Sphere` to constrain results. Radius defaults to 500 m and caps at 50 000 m.
  - `page`, `per_page` (same bounds as list).
- Results come from `_build_filtered_query`; they are ordered by `updated_at desc, place_id desc`.
- Standard response (local DB hits):
```json
{
  "results": [ { /* place record */ }, ... ],
  "meta": { "page": 1, "per_page": 20, "total": 5 }
}
```
- When no local rows exist for `q` (and `tag`, radius filters are absent, and `page == 1`), `_ingest_nominatim_places` calls the OpenStreetMap Nominatim API, stores any non-duplicate hits, and returns transient pins via `_serialize_transient_place`. These pins include `source: "nominatim"` and may lack `placeId`.

## Response Objects

### Pin (`place_to_pin`)
Used by POST/GET/PUT/list responses.

| Field | Description |
| ----- | ----------- |
| `id` / `placeId` | Integer identifier. |
| `name` | Original `Place.name`. |
| `label` | First non-empty value among `alt_name`, `name`, `display_name`. |
| `lat` / `lng` | Coordinates from the `coordinate` column. |
| `type` | Derived by `_derive_pin_type` using Nominatim-style categories and extratags, if present. |
| `tags` | Parsed dict/list from `Place.tags` (defaults to `{}` or `[]`). |
| `source` | `"place"` for persisted rows. |
| `createdAt`, `updatedAt` | ISO timestamps. |
| `raw` | The `Place.to_dict()` output for debugging. |

### Search Record (`place_to_dict`)
Returned by `/places/search` when local DB rows exist.

- `id` and `place_id` (both set)
- `name`, `alt_name`, `display_name`
- `description` (present or `null`)
- `tags` (list; forced to `[]` if missing)
- `geom` (always `null` to avoid leaking heavy geometries; frontends can fall back to `lat`/`lon`)
- `source: "place"`
- `created_at`, `updated_at`, and any extra columns present in the `Place` model

### Transient Search Pin (`_serialize_transient_place`)
Returned by `/places/search` when the server had to call Nominatim and nothing was saved yet.

- `id`/`placeId`: `null`
- `name`, `label`, `lat`, `lng`
- `type`: derived from tags
- `tags`: dictionary with `source: "nominatim"` plus whatever Nominatim provided
- `source`: `"nominatim"`
- `raw`: lightweight dict mirroring the payload

## Geospatial Handling
- All stored coordinates use SRID 4326 and are written into `Place.coordinate` as `POINT(lon lat)`.
- `_store_place_area` writes GeoJSON polygons directly into the spatial `geom` column when available; otherwise it caches the raw geometry in an `edges` JSON column.
- `_bbox_to_geojson_polygon` converts 4-value bboxes (`min_lon,min_lat,max_lon,max_lat` or their lat/lon counterpart) into a GeoJSON polygon, ensuring numeric values and valid extents.
- When only lat/lon are sent, the API still stores them even if `geom` is omitted; clients can reconstruct a point from `lat`/`lng` in response objects.

## External Ingestion (Nominatim)
- `NOMINATIM_SEARCH_URL` and `NOMINATIM_HEADERS` define a 5 s timeout search. The query includes address, extra tags, and name details to make `_derive_pin_type` more accurate.
- Each normalized result checks `_place_exists_nearby` (case-insensitive name match within ~0.0005°). Duplicates are skipped.
- Inserted rows are committed immediately; failures roll back and emit a warning, but the transient results are still returned to the client.

## Error Handling
- Validation issues return `400 {"message": "Invalid input", "errors": [...]}`.
- Missing IDs return `404 {"message": "Place not found"}`.
- Database write failures surface as `400 {"message": "Failed to <action> place", "error": "<db-error>"}`.
- Radius searches missing `lat` or `lon` respond with `400 {"message": "lat and lon are required for radius search"}`.

---

Generated directly from `apps/place/views.py`. Update this document whenever the view logic or serialization helpers change to keep API consumers aligned.
