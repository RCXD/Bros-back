### 모듈 개요

Flask 블루프린트 bp = Blueprint("route", __name__)를 중심으로, 위험물(hazard) 수집/집계, OSRM 산출물(CSV/Lua) 생성, osrm-customize 백그라운드 실행, 안전 경로 계산, 사용자 경로 CRUD를 제공합니다.
OSRM 연동은 nearest/route HTTP API와 로컬 바이너리(osrm-extract/partition/customize) 호출 두 축으로 구성됩니다.
OSRM 연동 유틸

최근접 엣지 조회: _match_osm_edge(lat, lon, ...)가 OSRM nearest를 호출해 osm:{a}-{b} 혹은 좌표 기반 토큰을 반환.
하자드→OSM 엣지 매핑: build_hazard_osm_edge_mapping(limit, ...)가 활성 하자드를 순회하며 osm_edge_id를 대량 업데이트.
CLI 보조: hazard_edge_matcher_cli(argv)로 앱 컨텍스트에서 일괄 매핑 실행.
하자드 CSV/Lua 생성

CSV 생성: export_hazard_penalties_csv(csv_path)가 활성 하자드를 엣지별 최대 penalty로 축약해 edge_id,penalty 형태 CSV 출력.
Lua 헬퍼: render_osrm_hazard_profile(csv_path, lua_path)가 CSV를 읽어 edge_id별 penalty 조회/적용 함수를 제공하는 Lua 모듈 생성.
일괄 생성: export_osrm_hazard_artifacts(csv_path, lua_path)로 CSV와 Lua 동시 재생성.
OSRM 파이프라인/커스터마이즈

전체 파이프라인: build_osrm_pipeline(pbf, profile, osrm, threads)가 osrm-extract → osrm-partition → osrm-customize를 차례로 실행.
단발 커스터마이즈: trigger_osrm_customize(osrm_path, threads)가 CSV/Lua 재생성 후 osrm-customize를 백그라운드 실행(중복 방지 락/플래그 포함).
디바운스 워커: _CustomizeWorker가 다수의 하자드 유입을 짧은 시간에 묶어 한 번만 CSV 재생성+osrm-customize 실행.
기본 디바운스 OSRM_CUSTOMIZE_DEBOUNCE(기본 2.0s).
실행 중복 방지 _OSRM_CUSTOMIZE_LOCK와 _OSRM_CUSTOMIZE_RUNNING 사용.
싱글톤으로 모듈 임포트 시 자동 시작, schedule_osrm_customize()로 외부에서 트리거.
입력/캐시/레이트리밋/벌점 유틸

입력 파싱: _parse_point, _parse_points_payload가 {lat, lon} 형태를 정규화.
레이트 리밋: _rate_limited(key)가 IP/사용자 단위 슬라이딩 윈도우 제한.
벌점 계산: _penalty_from_danger(danger_score)가 0–10 점수를 가중치(≥1.0)로 매핑.
하자드 캐시: _hazard_cache()가 활성 하자드를 엣지별 최대 penalty로 유지, TTL 기본 30초. 강제 갱신 _hazard_cache(force=True).
경로 샘플링/엣지 수집

거리: _haversine_km(p1, p2) 구면거리.
구간 엣지: _segment_edges(p1, p2)가 선분을 등분점으로 샘플링해 nearest 호출, 엣지 집합 수집.
전체 경로 엣지: _collect_route_edges(points)가 모든 구간 결과 합집합.
경로 벌점: _route_penalty(points)가 캐시된 penalty 합산.
API 엔드포인트

POST /route/hazards → ingest_hazard()
입력 검증, OSRM nearest로 엣지 매칭, DB 저장, 캐시 갱신, schedule_osrm_customize()로 디바운스 커스터마이즈 예약.
GET /route/hazard/active → 활성 하자드 목록 조회.
POST /route/hazard/refresh → 하자드 캐시 강제 갱신.
POST /route/hazard/map-osm-edges → 하자드의 엣지 매핑 일괄 갱신(백필).
POST /route/safe → safe_route()
OSRM route로 전체 경로를 구하고, geometry를 샘플링하여 엣지 집합을 만든 뒤 캐시 penalty를 합산. 거리/시간/벌점 및 경로 정보를 반환.
Paths CRUD (JWT 필요)
GET /route/paths → get_my_paths(): 내 경로 목록.
POST /route/paths → save_path(): 경로 저장.
GET /route/paths/<id> → get_path(): 경로 상세.
PUT /route/paths/<id> → update_path(): 경로 수정(포인트/이름).
DELETE /route/paths/<id> → delete_path(): 경로 삭제.
환경 변수/경로

OSRM 데이터/산출물: OSRM_DATA_DIR, OSRM_HAZARD_CSV, OSRM_HAZARD_LUA, OSRM_PROFILE_LUA, OSRM_PBF_PATH, OSRM_OSRM_PATH.
OSRM 서버: OSRM_BASE_URL(기본 http://localhost:5000), OSRM_PROFILE(기본 driving), 스레드 OSRM_THREADS.
커스터마이즈 디바운스: OSRM_CUSTOMIZE_DEBOUNCE.
동작 흐름 요약

하자드 수집 시: 입력 검증 → 최근접 엣지 매칭 → DB 저장 → 캐시 갱신 → 커스터마이즈 디바운스 트리거.
커스터마이즈 워커: 조용한 구간(디바운스) 후 CSV/Lua 재생성 → osrm-customize 한 번 실행(중복 방지).
안전 경로 계산: OSRM 경로 → geometry 샘플링→ 엣지 집합 → 캐시 벌점 합산 → 결과 반환.
테스트 팁

실제 OSRM 없이도 scripts\osrm-customize.cmd를 PATH에 둔 스텁으로 호출 여부를 로깅해 워커 활성화 확인 가능.
map.osrm 파일이 존재해야 워커가 customize를 시도합니다.