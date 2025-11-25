# ============================================
# Place module TODO resolution
# ============================================

- **Coordinates & geometry**: rewrote `_set_place_coordinate`, `_place_lat_lon`, `_store_place_area`, and `_validate_geojson` so point and polygon inputs always produce a valid SRID 4326 geometry while avoiding the legacy `edges` path.
- **Search & ingestion**: rebuilt `_normalize_nominatim_item`/`_ingest_nominatim_places`, added `_parse_tag_filter`, refreshed `_build_filtered_query`, and modernized `_apply_point_radius_filter` so local and Nominatim data produce consistent tags/geom ingestion plus JSON-aware tag filtering.
- **API responses**: `list_places`, `search_places`, `get_place`, `create_place`, and `update_place` now share `place_to_dict` output, while `place_to_pin` is preserved for compatibility; `place_to_dict` itself derives labels, `lng`, and type metadata from normalized tags.
- **Reverse geocoding**: added `_fetch_nominatim_reverse`, wired a `/place/reverse` endpoint, and normalized the response payload so clients can consume `reverse` metadata/geom just like search hits.
