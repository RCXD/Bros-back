# Bros-back

Flask 기반의 백엔드 프로젝트로, 소셜/로컬 탐색 서비스를 지원한다.  
인증, 게시물, 경로/장소, 결제, 알림 등의 기능을 각각 독립된 Blueprint 모듈로 구성했으며,  
공통 확장기능(SQLAlchemy, Flask-Migrate, CORS, JWT), 로깅, 정적 폴더 초기화는 `apps/app.py`에서 처리한다.

# 🚀 404found 1차 프로젝트

> **프로젝트의 모든 과정을 담은 상세 시연 영상입니다.** > 이미지 또는 버튼을 클릭하면 유튜브 페이지로 이동합니다.

<div align="center">
  <a href="https://www.youtube.com/watch?v=Y5KoIeUuco0">
    <img src="https://img.youtube.com/vi/Y5KoIeUuco0/maxresdefault.jpg" width="80%" alt="404found 시연영상">
    <br>
    <img src="https://img.shields.io/badge/YouTube-Watch_Video-red?style=for-the-badge&logo=youtube" alt="Youtube Button">
  </a>
</div>

## 📁 폴더 구조
```text
apps/
 ├─ app.py              # Flask 앱 팩토리 및 blueprint 등록
 ├─ config/             # 환경 변수 로딩 및 공통 설정
 │   ├─ common.py
 │   ├─ server.py
 │   └─ store_reward_control.json
 ├─ auth/               # 인증/로그인, OAuth, JWT
 ├─ user/               # 프로필, 팔로우, 친구 관리
 ├─ post/, reply/, feed/  # 게시글/댓글/피드
 ├─ route/, place/      # 경로 탐색, 장소 정보, 즐겨찾기
 ├─ cosmetic/, product/ # 장식 아이템, 상품, 구매 가능 자산
 ├─ payment/            # 카카오페이 결제 처리
 ├─ notification/, mention/   # 알림, 멘션 처리
 ├─ search/             # 검색 기록, 자동완성, 캐시
 ├─ admin/, report/     # 어드민 도구, 신고 처리
 ├─ roadview/           # 지도/로드뷰(Kakao, Google, Naver)
 ├─ image/, favorite/   # 이미지 업로드/서빙, 즐겨찾기 연결
 ├─ detector/, security/  # (선택/비활성) AI/보안 관련 기능
 ├─ logs/, static/      # 로그, 정적 리소스
 ├─ scripts/            # OSRM 빌드/테스트 스크립트
 └─ API_README.md       # 상세 API 문서

migrations/             # DB 마이그레이션 스크립트
static/                 # Flask에서 서빙하는 이미지/자산 저장소
logs/                   # 런타임 로그 출력
scripts/                # OSRM 및 기타 테스트 스크립트
osrm-test/              # OSRM 실험 기능 테스트
test/, test_legacy/     # pytest 및 레거시 테스트
기타 루트 파일: apply_item_type_migration.py, finish_mention_migration.py, .endpoint.env, setup_flask_env.ps1 등
```
---

## 🔑 핵심 기능 요약

| 기능 영역 | 설명 |
|-----------|------|
| Auth/User | JWT 로그인, OAuth 계정 유형, 프로필/팔로우/친구 |
| Posts/Replies | 게시글, 댓글, 좋아요, 멘션, 피드 생성 |
| Media/Image | 이미지 업로드, 경로/상품/프로필/코스메틱 서빙 |
| Places/Routes | 장소 검색, reverse geocoding, 경로 계산, OSRM |
| Commerce | 상품(코스메틱), 카카오페이 결제 플로우 |
| Notification/Mention | 알림 시스템, 읽음 관리, 멘션 트리거 |
| Search | 검색 기록, 자동완성, 캐싱 |
| Admin/Report | 관리자 도구, 유저/콘텐츠 신고 관리 |
| Data Migration | Flask-Migrate 및 수동 DB migration 스크립트 |

---

## 📌 Blueprint와 엔드포인트 (URL Prefix → Module)

| Prefix | Module 설명 |
|--------|-------------|
| `/auth` | 로그인, 회원가입, 토큰 재발행, OAuth |
| `/user` | 프로필, 팔로우, 유저 정보 |
| `/post`, `/reply` | 게시물/댓글 CRUD, 좋아요, 멘션 |
| `/feed` | 소셜 피드, 팔로우 기반 콘텐츠 |
| `/place`, `/route` | 장소 검색/저장, 경로 탐색, 즐겨찾기 |
| `/cosmetic`, `/product` | 코스메틱 아이템, 상품, 소장/구매 |
| `/payment` | 카카오페이 결제/승인/취소 |
| `/notification`, `/mention` | 실시간 알림, 멘션 트리거 |
| `/roadview` | 지도/로드뷰 (Google/Naver/Kakao) |
| `/search` | 검색 기록, 자동완성 |
| `/admin` | 관리자 전용 관리/모니터링 |
| `/report` | 신고 관리 |

---

## 🚀 Setup

1. Python 3.10+ 설치 및 가상환경 활성화

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```
2. .env.local 또는 .env 생성 후 환경 변수 입력
3. DB 마이그레이션 실행
flask --app apps.app db upgrade
4. (선택) 코스메틱 아이템 Seed 실행
flask --app apps.app seed-cosmetics

▶ 실행 방법
| 모드 | 명령어 | 설명
|--------|--------|-------|
|개발(local) | python apps/app.py --local | .env.local 자동 로드, 기본 포트 8001
|운영(prod)	| python apps/app.py --prod	| 실제 배포 환경과 유사한 설정
|Debug 강제 활성화 | --debug | 개발 편의 모드

🧪 Tests
pytest

## ⚙️ 주요 환경 변수
| 영역 | 변수 이름 |
|--------|---------|
| Flask 기본 | FLASK_HOST, FLASK_PORT, FLASK_DEBUG, SECRET_KEY
| Database | DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME
| JWT 설정 | JWT_SECRET_KEY, JWT_ACCESS_TOKEN_EXPIRES_HOURS, JWT_TOKEN_LOCATION
| CORS/Session | CORS_ORIGINS, SESSION_COOKIE_SAMESITE, SESSION_COOKIE_SECURE
| Static/File	| UPLOAD_FOLDER, STATIC_FOLDER, MAX_CONTENT_LENGTH_MB
| KakaoPay | KAKAO_ADMIN_KEY, KAKAO_APPROVAL_URL, KAKAO_FAIL_URL, CID
| 외부 지도 API | GOOGLE_MAPS_API_KEY, KAKAO_REST_API_KEY, NAVER_CLIENT_ID

## 사용 라이브러리
- [Flask-JWT-Extended](https://flask-jwt-extended.readthedocs.io/en/stable/) - JWT 인증 및 토큰 발급/검증
- [OSRM Backend](https://github.com/Project-OSRM/osrm-backend) - 경로 계산과 라우팅 엔진
- [GeoAlchemy2](https://geoalchemy-2.readthedocs.io/en/latest/) - 공간 데이터 처리를 위한 SQLAlchemy 확장

## API
- [Kakao Mobility API](http://xn--dvelopers-bo44b.kakaomobility.com/product/api) - 카카오 모빌리티/지도 API 연동
