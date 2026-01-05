```python
from apps.route.route_module_check import check_route_module

# Quick sanity check for the endpoints documented below.
check_route_module()
```

# Route Module Specification

## 개요

Flask 블루프린트 `bp = Blueprint("route", __name__)`를 중심으로 위험물(hazard) 수집/집계, OSRM 산출물(CSV/Lua) 생성, `osrm-customize` 백그라운드 실행, 안전 경로 계산, 사용자 경로 CRUD 기능을 제공합니다. OSRM 연동은 HTTP API(`nearest`, `route`)와 로컬 바이너리(`osrm-extract`, `osrm-partition`, `osrm-customize`) 호출로 구성됩니다.

## OSRM 연동 유틸

- **최근접 엣지 조회**: `_match_osm_edge(lat, lon, ...)`는 OSRM `nearest`를 호출하여 `osm:{a}-{b}` 또는 좌표 기반 토큰을 반환합니다.
- **하자드→OSM 엣지 매핑**: `build_hazard_osm_edge_mapping(limit, ...)`은 활성 하자드를 순회하며 `osm_edge_id`를 대량 업데이트합니다.
- **CLI 보조**: `hazard_edge_matcher_cli(argv)`는 앱 컨텍스트에서 일괄 매핑 실행을 위한 진입점입니다.

## 하자드 CSV/Lua 생성

- **CSV 생성**: `export_hazard_penalties_csv(csv_path)`는 활성 하자드를 엣지별 최대 penalty로 축약하여 `edge_id,penalty` 형태 CSV를 출력합니다.
- **Lua 헬퍼**: `render_osrm_hazard_profile(csv_path, lua_path)`는 CSV를 읽어 `edge_id`별 penalty 조회/적용 함수를 제공하는 Lua 모듈을 생성합니다.
- **동시 생성**: `export_osrm_hazard_artifacts(csv_path, lua_path)`는 CSV와 Lua를 동시에 재생성합니다.

## OSRM 파이프라인 및 커스터마이즈

- **전체 파이프라인**: `build_osrm_pipeline(pbf, profile, osrm, threads)`는 `osrm-extract` → `osrm-partition` → `osrm-customize`를 순차적으로 실행합니다.
- **단발 커스터마이즈**: `trigger_osrm_customize(osrm_path, threads)`는 CSV/Lua 재생성 후 `osrm-customize`를 백그라운드에서 실행하며 락/플래그로 중복 실행을 방지합니다.
- **디바운스 워커**: `_CustomizeWorker`는 다수 하자드 유입을 짧은 시간에 묶어 CSV를 한 번만 재생성하고 `osrm-customize`를 실행합니다. 디바운스 간격은 `OSRM_CUSTOMIZE_DEBOUNCE`(기본 2.0초)이며 `_OSRM_CUSTOMIZE_LOCK`과 `_OSRM_CUSTOMIZE_RUNNING`으로 실행 중복을 차단합니다. 모듈 임포트 시 싱글톤으로 자동 시작되며 `schedule_osrm_customize()`로 외부 트리거도 지원합니다.

## 입력 · 캐시 · 레이트리밋 · 벌점

- **입력 파싱**: `_parse_point`, `_parse_points_payload`는 `{lat, lon}` 형태를 정규화합니다.
- **레이트 리밋**: `_rate_limited(key)`은 IP/사용자 단위 슬라이딩 윈도우 제한을 적용합니다.
- **벌점 계산**: `_penalty_from_danger(danger_score)`는 0–10 점수를 가중치(≥1.0)로 맵핑하여 벌점 값을 도출합니다.
- **하자드 캐시**: `_hazard_cache()`는 활성 하자드를 엣지별 최대 penalty로 유지하고 TTL은 기본 30초입니다. `force=True`로 강제 갱신이 가능합니다.

## 경로 샘플링 및 엣지 수집

- **거리 계산**: `_haversine_km(p1, p2)`는 두 좌표 사이의 구면거리를 계산합니다.
- **구간 엣지 추출**: `_segment_edges(p1, p2)`는 선분을 등분점으로 샘플링해 `nearest` 호출 후 엣지 집합을 수집합니다.
- **전체 경로 엣지**: `_collect_route_edges(points)`는 모든 구간 결과의 합집합을 만듭니다.
- **경로 벌점**: `_route_penalty(points)`는 캐시된 penalty 값을 합산합니다.

## API 엔드포인트

- `POST /route/hazards` → `ingest_hazard()`: 입력 검증 → `nearest` 호출로 엣지 매칭 → DB 저장 및 캐시 갱신 → `schedule_osrm_customize()`로 디바운스 커스터마이즈 예약.
- `GET /route/hazard/active` → 활성 하자드 목록 조회.
- `POST /route/hazard/refresh` → 하자드 캐시 강제 갱신.
- `POST /route/hazard/map-osm-edges` → 하자드 엣지 매핑 일괄 갱신(백필).
- `POST /route/safe` → `safe_route()`: OSRM `route`로 전체 경로 추출 → geometry 샘플링 → 엣지 집합 수집 → 캐시 벌점 합산 → 거리/시간/벌점/경로 정보 반환.

### Paths CRUD (JWT 필요)

- `GET /route/paths` → `get_my_paths()`: 사용자 경로 목록 조회.
- `POST /route/paths` → `save_path()`: 경로 저장.
- `GET /route/paths/<id>` → `get_path()`: 경로 상세 조회.
- `PUT /route/paths/<id>` → `update_path()`: 포인트/이름 수정.
- `DELETE /route/paths/<id>` → `delete_path()`: 경로 삭제.

## 환경 변수 및 경로

- **OSRM 데이터/산출물**: `OSRM_DATA_DIR`, `OSRM_HAZARD_CSV`, `OSRM_HAZARD_LUA`, `OSRM_PROFILE_LUA`, `OSRM_PBF_PATH`, `OSRM_OSRM_PATH`.
- **OSRM 서버**: `OSRM_BASE_URL`(기본 `http://localhost:5000`), `OSRM_PROFILE`(기본 `driving`), 작업 스레드 `OSRM_THREADS`.
- **커스터마이즈 디바운스**: `OSRM_CUSTOMIZE_DEBOUNCE`.

## 동작 흐름 요약

- **하자드 수집**: 입력 검증 → `nearest` 엣지 매칭 → DB 저장 → 캐시 갱신 → 커스터마이즈 디바운스 트리거.
- **커스터마이즈 워커**: 디바운스 구간 종료 후 CSV/Lua 재생성 → 한 번만 `osrm-customize` 실행(중복 방지).
- **안전 경로 계산**: `route` 호출 → geometry 샘플링 → 엣지 집합 생성 → 캐시 벌점 합산 → 결과 반환.

## 테스트 팁

- 실제 OSRM 없이도 `scripts\osrm-customize.cmd`를 `PATH`에 둔 스텁으로 호출 여부를 로깅해 워커 활성화를 확인할 수 있습니다.
- `map.osrm` 파일이 존재해야 워커가 `customize`를 시도합니다.
