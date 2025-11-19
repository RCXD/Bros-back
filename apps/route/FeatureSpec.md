# TODO: 내가 준 SRS 그대로 구현해. KSLink 로더, 매핑 스크립트, UTIC ingest, TrafficHazard, OSRM CSV/Lua 통합까지 전체 코드 생성해.
📘 KS Node-Link + UTIC 실시간 소통정보 → OSRM 라우팅 반영
상세 기술 명세서 (SRS for CODEX)
1. System Overview

본 시스템은 다음 데이터를 통합하여 OSRM 라우팅 비용을 실시간으로 조정한다.

KS Node-Link 국가표준 도로망

UTIC(경찰청 도시교통정보센터) 실시간 소통정보

OSRM edge 기반 경로 비용(weight) 커스터마이즈

기본 전략은 다음과 같다:

KS Node-Link → OSM edge 매핑(초기 1회)
UTIC linkId별 속도·통행상태 수집(실시간)
↓
TrafficHazard(edge penalty) DB 업데이트
↓
hazard_penalties.csv / hazard_penalties.lua 자동 생성
↓
osrm-customize 자동 트리거
↓
safe_route()에서 실시간 교통 반영


이미 프로젝트에 존재하는 hazard 시스템(OSRM 커스터마이즈 파이프라인)을 그대로 재사용한다.

2. 데이터 모델 정의
2.1 KSLink (국가표준 링크 DB)

KS Node-Link에서 로딩한 국가 표준 링크 저장.

class KSLink(db.Model):
    __tablename__ = "ks_links"

    link_id = db.Column(db.String(32), primary_key=True)  # KS Node-Link의 LINK_ID
    f_node = db.Column(db.String(32))
    t_node = db.Column(db.String(32))

    # 좌표 배열: [[lon, lat], [lon, lat], ...]
    geom = db.Column(JSON, nullable=False)

    # 이 KS-Link가 매핑된 OSM edge 목록
    osm_edges = db.Column(JSON)  # ["osm:123-456", "osm:456-789", ...]

요구 사항

geom: 최소 2개 이상의 좌표

osm_edges는 초기 null이며, “OSRM nearest 매핑 단계”에서 채워짐

link_id + osm_edges 조합에 인덱스 필요 (검색 성능 개선)

2.2 TrafficHazard (실시간 소통정보 penalty 저장)
class TrafficHazard(db.Model):
    __tablename__ = "traffic_hazards"

    id = db.Column(db.Integer, primary_key=True)
    link_id = db.Column(db.String(32), index=True)        # KS-Link ID
    osm_edge_id = db.Column(db.String(64), index=True)    # OSRM edge
    penalty = db.Column(db.Float, nullable=False)         # multiplicative weight
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

요구 사항

동일 edge에 대해 가장 최신값 유지

stale penalty는 3~5분 이후 자동 무효화 (예: 주기적 cleanup)

TrafficHazard는 Hazard와 동일한 penalty 시스템에 합산됨

3. KS Node-Link → DB 로딩 스펙
3.1 입력 데이터

국가교통DB 제공 KS Node-Link SHP 또는 CSV

필드 예: LINK_ID, F_NODE, T_NODE, geometry(WKT 또는 SHP polyline)

3.2 로딩 규칙

geometry를 lon, lat 순서 배열로 변환하여 JSON으로 저장

다중 파트 geometry는 단일 polyline으로 merge (보통 KS-Link는 단일 선)

linkId는 문자열로 저장

4. KS-Link → OSM Edge 매핑
4.1 매핑 함수 규격
def map_kslink_to_osm_edges(kslink: KSLink) -> list[str]

입력

KSLink 인스턴스

kslink.geom: [[lon, lat], ...]

처리

geometry 길이를 N이라 할 때,
모든 구간 geom[i] → geom[i+1] 에 대해 _segment_edges(p1, p2) 실행

_segment_edges() 내부의 _match_osm_edge()는 OSRM /nearest API 호출

출력

중복 제거된 OSM edge 목록

edge 형식: osm:{a}-{b}

저장 규칙

kslink.osm_edges = list(edges)

DB에 즉시 commit

4.2 수행 정책

최초 1회 전체 KS-Link 대상 batch 매핑

배치 스크립트 형태:

for each KSLink:
    if osm_edges is empty:
        map_kslink_to_osm_edges(kslink)


작업량 많음 → 백그라운드 batch로 돌릴 것

매핑 실패 시 retry 로깅

5. UTIC 실시간 소통정보 처리
5.1 API 호출 모듈
엔드포인트 예시
GET https://apis.data.go.kr/1613000/UTIC/trafficLink?
    serviceKey=...
    &type=json
    &numOfRows=10000

응답 예
{
    "linkId": "L1234567",
    "speed": "24",
    "traffic": "서행",
    "travelTime": "310"
}

5.2 데이터 파서
def parse_utic_payload(item):
    return {
        "link_id": item["linkId"],
        "speed": float(item["speed"]),
        "traffic": item.get("traffic"),
        "travel_time": float(item.get("travelTime", 0)),
    }

6. UTIC → TrafficHazard 반영 로직
6.1 속도 기반 penalty 계산
def traffic_penalty(speed):
    if speed > 40: return 1.0      # 원활
    if speed > 20: return 1.2      # 서행
    if speed > 10: return 1.5      # 정체
    if speed > 0:  return 2.0      # 극심한 정체
    return 3.0                     # 통제 or 속도=0

6.2 연산 규칙
def ingest_utic_item(item):
    data = parse_utic_payload(item)

    ks = KSLink.query.get(data["link_id"])
    if not ks or not ks.osm_edges:
        log("Missing KSLink or no OSM edges", data["link_id"])
        return False

    penalty = traffic_penalty(data["speed"])

    for edge in ks.osm_edges:
        row = TrafficHazard.query.filter_by(osm_edge_id=edge).first()

        if not row:
            row = TrafficHazard(
                link_id=data["link_id"],
                osm_edge_id=edge,
                penalty=penalty
            )
            db.session.add(row)
        else:
            row.penalty = penalty

    db.session.commit()
    schedule_osrm_customize()  # 디바운스 커스터마이즈
    return True

7. OSRM Penalty 통합 (CSV/Lua)
7.1 수정 대상: export_hazard_penalties_csv()

TrafficHazard 포함하도록 확장:

traffic = TrafficHazard.query.with_entities(
    TrafficHazard.osm_edge_id,
    TrafficHazard.penalty
).all()

for edge, penalty in traffic:
    penalties[edge] = max(penalties.get(edge, 0), penalty)

규칙:

동일 edge에 대해 hazard.penalty와 traffic.penalty 중 더 큰 값 사용

CSV 컬럼 그대로 유지:

edge_id,penalty
osm:123-456,1.40
...

8. Customize 파이프라인 (기존 그대로 사용)

이미 존재하는 pipeline 유지:

export_osrm_hazard_artifacts()

osrm-customize (-t THREADS)

_CustomizeWorker 디바운스 처리

요구 사항

customize-only이므로 extract/partition 재실행 불필요

hazard CSV/Lua만 갱신하면 됨

9. safe_route() 적용 스펙

safe_route 과정은 그대로 사용한다.
TrafficHazard가 hazard_cache에 포함되면 자동 반영됨.

변경 사항

_hazard_cache() 로딩 시 TrafficHazard도 포함하도록 확장

travel_weight 계산
travel_weight = distance_km + hazard_penalty
hazard_penalty = sum(penalty for each edge in route)

10. Stale 데이터 만료 정책

정책:

TrafficHazard.updated_at 기준 3~5분 이상 지난 penalty는 무효

cleanup 스크립트:

def cleanup_stale_traffic(minutes=5):
    cutoff = datetime.utcnow() - timedelta(minutes=minutes)
    TrafficHazard.query.filter(
        TrafficHazard.updated_at < cutoff
    ).delete()
    db.session.commit()


주기: 2~5분마다 실행

11. 테스트 시나리오
11.1 KS-Link → OSM Mapping 테스트

KSLink 10개 샘플 선택

_segment_edges() 정상 작동 여부

OSM edge 정상 생성 여부 확인

11.2 UTIC Traffic ingest 테스트

속도=50 → penalty=1.0

속도=12 → penalty=1.5

속도=0 → penalty=3.0

CSV 생성에 penalty 반영 여부 확인

11.3 Customize 테스트

여러 hazard/traffic 업데이트 → customize 1회만 발생해야 함

customize.log에서 호출 기록 확인

11.4 Routing 테스트

정체 구간(edge penalty > 1.5) 우회 여부

distance 짧지만 정체 penalty 큰 경우 OSRM이 우회 경로 선택하는지 검증

12. 디렉터리 구조 권장안
apps/
  route/
    models.py (KSLink, TrafficHazard 추가)
    traffic_ingest.py (UTIC API fetch + ingest)
    kslink_mapping.py (KSLink→OSM edge 매핑 작업)
    views.py (safe_route 기존 유지)
    hazard_pipeline.py (CSV/Lua + customize)

13. 운영 환경 요구사항

OSRM 서버 실행

/nearest API 반응 속도 < 50ms

customize 스레드 동시 실행 방지됨

UTIC API key 필요

KS Node-Link 전처리 파일 필요

14. 성능 고려사항

KS-Link 전체 매핑은 3천~7천 링크 → 1회 약 수 분

Traffic penalty ingest는 초당 수십건까지 처리 가능

customize 디바운스 2초 설정 추천

hazard_cache TTL 30초 유지

15. 보안 / 예외 상황 처리

UTIC API timeout 1~2초

linkId 미존재 → 로깅 후 skip

osrm-customize 실패 시 자동 재시도

stale 데이터 존재 시 penalty 중첩 방지