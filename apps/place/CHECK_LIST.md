실행 가능한 체크리스트 (빠르게 적용)
==================================

DB 준비
------

- [ ] MySQL 8 이상에서 실행 중인지 확인한다.

컬럼/데이터 정합성
------------------

- [ ] 모든 지리 좌표를 GeoJSON 표준([lon, lat])로 받고 geom 컬럼은 SRID=4326으로 지정한다.
- [ ] 신규 좌표 입력 시 아래 SQL 패턴을 이용한다.

```sql
INSERT INTO places (name, geom)
VALUES ('한강', ST_SetSRID(ST_GeomFromText('POINT(126.9780 37.5665)'), 4326));
```

인덱스
-----

- [ ] geom 컬럼에 SPATIAL 인덱스를 생성하고(MySQL 8 InnoDB 지원 여부 확인) 쿼리 플랜을 통해 사용 여부를 검증한다.

```sql
ALTER TABLE places ADD SPATIAL INDEX idx_places_geom (geom);
```

빠른 bbox 쿼리
------------

- [ ] 후보 좁히기는 MBRIntersects(또는 지원 시 ST_Intersects)로 처리한다.

```sql
SELECT id, name, ST_AsGeoJSON(geom) AS geom_geojson
FROM places
WHERE MBRIntersects(
  geom,
  ST_GeomFromText('POLYGON((lonmin latmin, lonmax latmin, lonmax latmax, lonmin latmax, lonmin latmin))')
);
```

근접(Nearest) 검색
----------------

- [ ] KNN이 없다면 bbox로 후보를 줄인 뒤 ST_Distance 기준 정렬로 대응한다.

```sql
SELECT id, name, ST_AsGeoJSON(geom) AS geom_geojson,
       ST_Distance(geom, ST_SetSRID(ST_GeomFromText('POINT(lon lat)'), 4326)) AS dist
FROM places
WHERE MBRIntersects(geom, ST_GeomFromText('POLYGON(...)')) -- 작은 bbox
ORDER BY dist
LIMIT 1;
```

프론트 연동
---------

- [ ] 응답 시 ST_AsGeoJSON(geom)으로 문자열화하여 JSON payload로 전달하고, 프론트는 파싱 후 GeoJSON 객체로 사용한다.

캐시/성능
-------

- [ ] 동일 bbox 요청에 짧은 TTL(1~5분) 캐시를 적용한다.
- [ ] per_page를 최대 500 정도로 제한하고 페이징을 강제한다.

확장 대비
-------

- [ ] 공간 쿼리는 서비스 계층 추상화(예: `placeService.findInBbox(bbox)`)로 감싸 후일 PostGIS 전환 시 구현체만 교체한다.

주의/제한점
--------

- [ ] KNN 성능이 떨어지므로 대량 후보에서는 반드시 bbox 선필터를 강제한다.
- [ ] 고급 지리 연산은 PostGIS 쪽이 우수함을 인지하고 범위를 정한다.
- [ ] SRID/좌표축 순서 및 GeoJSON vs WKT 포맷 혼동을 사전에 점검한다.
