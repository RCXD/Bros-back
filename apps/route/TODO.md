# TODO: 지도 화면에 보이는 영역 내 Hazard / Place 일괄 조회 구현

목표
- 현재 보이는 지도 영역(view bounds)을 계산해서 그 영역 안에 존재하는 `Hazard`와 `Place`를 모두 가져온다.
- 프론트는 사용자 경험을 우선으로 하되, 백엔드(DB, PostGIS)에 bbox 쿼리를 넘겨 DB 우선으로 결과를 받아온다. 실패 시 폴백(빈 배열 또는 외부 API)을 사용한다.

요약 워크플로우
1. 지도(Leaflet)에서 `map.getBounds()`로 현재 보이는 영역을 구한다.
2. bounds를 bbox 문자열로 직렬화(예: `lonmin,latmin,lonmax,latmax`)한다.
3. `fetchPlaces`(이미 존재함)와 유사한 `fetchHazards` 함수를 만들어 서버에 `?bbox=` 쿼리로 요청한다.
4. 응답(또는 `results` envelope)을 정규화한 뒤 Redux에 `setPinMarkers` / `setHazardMarkers` 등으로 저장한다.
5. 지도 이동/줌(이벤트: `moveend`, `zoomend`)에 디바운스(예: 200~400ms)로 재요청한다.
6. 페이징/수량 제한: 한번에 많은 데이터를 요청하지 않도록 `per_page` 또는 `limit` 파라미터를 사용한다.
7. 성능: 서버는 PostGIS GiST 인덱스, 프론트는 클라이언트 캐시/TTL을 사용한다.

권장 백엔드 엔드포인트 (블루프린트)
- GET `/place/search` 또는 `/places`
  - 쿼리: `?bbox=lonmin,latmin,lonmax,latmax&page=1&per_page=100&tag=...&q=...`
  - 응답: `{ results: [ { id, name, display_name, geom (GeoJSON), tags, source, ... } ], meta: { page, per_page, total } }` 또는 배열 직접 반환(프론트는 둘 다 허용)
- GET `/hazards` (혹은 `/hazard/search`)
  - 쿼리: `?bbox=lonmin,latmin,lonmax,latmax&page=1&per_page=100&min_score=...`
  - 응답: `{ results: [ { id, lat, lon, danger_score, geom (GeoJSON optional), ... } ], meta: {...} }`

백엔드 권장사항
- `geom` 필드는 PostGIS Geometry(Point, 4326)로 저장하고, 응답 시 `ST_AsGeoJSON(geom)`으로 GeoJSON을 반환.
- 인덱스: `CREATE INDEX ON places USING GIST(geom);` 및 hazards에 대해서도 GiST 인덱스 생성.
- bbox 검색: `ST_MakeEnvelope(lonmin, latmin, lonmax, latmax, 4326)`과 `ST_Intersects(geom, envelope)` 사용.
- 캐싱: 같은 bbox에 대해 짧은 TTL(예: 1~5분) 캐시를 적용하면 외부 API 폴백 호출을 줄일 수 있음.
- 응답 포맷 통일: `results` envelope 권장.

프론트엔드 구현 세부 (React + React-Leaflet)
1) 지도 바운드 계산(Leaflet)
- 사용 예시:
```js
const bounds = map.getBounds();
const sw = bounds.getSouthWest();
const ne = bounds.getNorthEast();
const bbox = `${sw.lng},${sw.lat},${ne.lng},${ne.lat}`; // lonmin,latmin,lonmax,latmax
```

2) 데이터 요청 함수 예시 (`src/pages/route/components/placeService.js`와 유사하게)
- `fetchPlaces`가 이미 있으면 동일한 패턴으로 `fetchHazards` 추가.
# TODO: 프런트엔드 변경 목록 — 백엔드 `place`/`route` API 기준

목표
- 백엔드의 `PLACE` 및 `ROUTE` API(`PLACE_API.md`, `ROUTE_API.md`)를 활용하도록 프런트엔드를 정렬합니다.
- 지도(view bounds) 범위 기반 데이터(Places, Hazards)를 빠르게 조회하고, CRUD 연동 및 클라이언트 상태를 일관성 있게 유지합니다.

요구사항 요약 (프론트에서 추가/변경/삭제할 항목)

1) 서비스(HTTP) 레이어 추가/변경
- 추가: `src/pages/route/components/placeService.js` — 기존 `fetchPlaces` 확장 또는 새로운 유틸로 유지
  - 함수: `fetchPlaces({ bbox, page, perPage, q, tag })` — 서버 `/place` 또는 `/place/search` 사용
  - 추가: `fetchHazards({ bbox, page, perPage, min_score })` — 서버 `/hazards` 또는 `/hazard/active` 사용
  - 기존: `Nominatim.jsx`는 이미 백엔드 우선으로 변경됨(완료). 서비스 함수는 백엔드 스키마(응답 envelope `results` 또는 `items`)를 정규화하도록 구현

2) `src/config/request_config.js` 업데이트
- 변경: 새 엔드포인트 상수 추가
  - `API.PLACE.SEARCH` → `/place/search` (또는 `/place` list)
  - `API.HAZARD.SEARCH` → `/hazards` 또는 `/hazard/active` (프로젝트 엔드포인트명과 일치 시 사용)

3) Redux 상태/액션 보완
- 추가/변경: `src/redux/mapSlice.js`
  - 상태 추가(또는 확인): `hazardMarkers` 또는 `hazards` (배열)
  - 액션: `setHazardMarkers(hazards)`, `clearHazardMarkers()`
  - 이미 존재하는 `pinMarkers` 관련 액션(`setPinMarkers`)이 있으므로, 서버에서 온 places를 `setPinMarkers`로 병합/업데이트

4) 지도 바운드 기반 자동 로드
- 변경: `MyRoute.jsx`에 `moveend` / `zoomend`(또는 `react-leaflet` 훅) 바인딩 적용
  - 디바운스(200~400ms) 적용
  - 기본 flow: `bbox = map.getBounds()` → `Promise.all([fetchPlaces({bbox}), fetchHazards({bbox})])` → dispatch
  - 초기 로드 시 한 번만 호출하도록 기존 `loadedPlaces` 로직과 통합(중복 요청 방지)

5) 데이터 정규화 및 병합
- 서버 응답(둘 다 허용): `results` envelope 또는 배열
- 정규화 함수 예: `normalizePlace(p)` / `normalizeHazard(h)` (id를 문자열로, lat/lon 추출 등)
- 병합: 클라이언트 로컬 마커(사용자 생성)와 서버 결과는 `id` 기반으로 병합(중복 방지)

6) UI 변경(선택적/권장)
- 대규모 데이터에서 성능: 마커 클러스터링 도입(react-leaflet-markercluster)
- 로딩 상태 표시: 맵 상단/사이드바에 간단한 스피너 또는 얇은 로딩 바
- 줌 레벨 정책: 너무 넓을 때(예: zoom < 12)에는 요청하지 않도록 제한

7) CRUD 연동(관리자용)
- 구현: 관리자 UI에서 `POST /place`, `PUT /place/<id>`, `DELETE /place/<id>`를 호출하는 화면/모달 필요시 추가
- 프론트 검증: `name`, `lat`, `lon` 필수 체크

8) 기존 모달/마커 흐름과의 연계
- `MarkerEditModal.jsx` 및 `MyRoute`의 핀/해저드 저장 로직은 기존 `POST /hazards`를 사용하도록 되어 있음 — 확인 필요
- Places는 별개(관리용)일 가능성이 높으므로 UI 흐름 상 places 생성은 관리자 전용으로 분리 권장

9) 에러 처리 및 폴백
- 백엔드 실패 시: 빈 배열을 사용하고(또는 캐시된 결과 사용) Nominatim 등 외부 폴백 호출은 서버에서 관리하도록 권장

10) 테스트/검증
- 자동화: E2E/통합 테스트 시나리오
  - 지도 범위를 특정 bbox로 옮겼을 때 `/place/search`와 `/hazards` 호출 발생
  - 응답 후 Redux state가 `pinMarkers`, `hazardMarkers`로 갱신
  - Marker 클릭/편집/삭제가 의도대로 동작

구체적 구현 항목(작업화 가능한 TODO)

- [ ] `src/config/request_config.js`에 `API.PLACE.SEARCH` 및 `API.HAZARD.SEARCH` 추가
- [ ] `src/pages/route/components/placeService.js` 만들기/확장: `fetchPlaces`, `fetchHazards` 구현 및 응답 정규화
- [ ] `src/redux/mapSlice.js`에 `hazardMarkers` 상태와 액션(`setHazardMarkers`) 추가
- [ ] `MyRoute.jsx`에 `map.on('moveend','zoomend')` 바인딩 및 디바운스 로직 추가 (초기 로드과 충돌 없이 통합)
- [ ] `Nominatim.jsx`(완료)와 `placeService`의 응답 포맷 정합성 확인
- [ ] `Marker` 관련 컴포넌트(예: `HazardMarker.jsx`, `PinMarker.jsx`)가 서버에서 내려온 `id`를 기준으로 정상 동작하는지 검증
- [ ] (선택) 마커 클러스터링 도입 및 렌더 성능 개선
- [ ] (선택) 관리자 UI: Place CRUD 모달/페이지 추가(권한 확인 필요)

데이터 샘플(프론트가 기대할 형태)
- Place (프론트 정규화 후):
  {
    id: "123",
    name: "한강공원",
    lat: 37.5665,
    lon: 126.9780,
    geom: { type: "Point", coordinates: [126.9780, 37.5665] },
    raw: { /* 원시 서버 응답 */ }
  }

- Hazard:
  {
    id: "h-456",
    lat: 37.56,
    lon: 126.98,
    danger_score: 5.2,
    raw: { /* 원시 서버 응답 */ }
  }

릴리즈/검증 단계
- 단계 1: 서비스 함수(`fetchPlaces`, `fetchHazards`) 구현 및 로컬 테스트
- 단계 2: `MyRoute`에 바인딩 적용, 네트워크 호출 확인
- 단계 3: Redux 상태 반영 확인 및 UI 반영(마커 표시)
- 단계 4: 성능/UX 튜닝(클러스터링, 로딩 표시)

지원 가능 작업(원하시면 제가 대신 구현해 드리겠습니다)
- A) `fetchHazards` 구현 및 `request_config.js`에 경로 추가
- B) `MyRoute.jsx`에 move/zoom 바인딩 및 디바운스 로직 적용
- C) `mapSlice`에 `hazardMarkers` 추가 및 관련 컴포넌트 리팩터

