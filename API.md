🌐 서버 연결 및 환경 설정

📡 서비스 기본 주소 (Base URL)

| **구분** | **서버 주소** | **비고** |
| --- | --- | --- |
| 🚀 | `http://localhost:8001` | 로컬 개발 환경 기본 주소 |
| 🛠️ | `http://0.0.0.0:8001` | 외부 기기 및 네트워크 접속 주소 |

⚙️ 서버 환경 변수 설정

운영 환경에 따라 아래 설정을 통해 서버 주소와 포트를 커스터마이징할 수 있습니다.

```bash
# 서버 호스트 및 포트 설정
export FLASK_HOST=0.0.0.0
export FLASK_PORT=8001

# 디버그 모드 설정 (개발 시 필수)
export FLASK_DEBUG=True
```

---

🔑 인증 및 보안 관리

| **방식** | **엔드포인트** | **설명** |
| --- | --- | --- |
| POST | `/auth/user` | 신규 사용자 계정 생성 (회원가입) |
| POST | `/auth/login` | 통합 로그인 게이트웨이 (일반/소셜) |
| POST | `/auth/login/google` | 구글 계정 연동 로그인 |
| POST | `/auth/login/kakao` | 카카오 계정 연동 로그인 |
| POST | `/auth/login/naver` | 네이버 계정 연동 로그인 |
| PUT | `/auth/user` | 사용자 프로필 및 계정 정보 수정 |
| DELETE | `/auth/logout` | 로그아웃 및 토큰 무효화 처리 |
| DELETE | `/auth/user` | 회원 탈퇴 및 데이터 논리 삭제 |
| POST | `/auth/refresh` | 토큰 만료 시 Access 토큰 재발급 |
| GET | `/auth/me` | 현재 접속 중인 사용자 정보 확인 |

👤 사용자 관계 및 멤버십 서비스

| **방식** | **엔드포인트** | **설명** |
| --- | --- | --- |
| GET | `/user/<id>` | 특정 사용자의 상세 프로필 데이터 조회 |
| GET | `/user/<id>/posts` | 특정 사용자가 작성한 게시물 피드 추출 |
| GET | `/user/search` | 사용자 닉네임/아이디 기반 통합 검색 |
| POST | `/user/follow/<id>` | 상대방 팔로우 관계 생성 |
| DELETE | `/user/follow/<id>` | 팔로우 관계 해제 |
| GET | `/<id>/followers` | 나를 팔로우하는 사용자 목록 조회 |
| GET | `/<id>/following` | 내가 팔로우 중인 사용자 목록 조회 |
| POST | `/user/friend/<id>` | 양방향 친구(이웃) 관계 요청 |
| DELETE | `/user/friend/<id>` | 친구 관계 삭제 |
| GET | `/<id>/friends` | 서로 이웃 관계인 사용자 목록 조회 |

📝 게시물 및 소셜 소통 시스템

| **방식** | **엔드포인트** | **설명** |
| --- | --- | --- |
| POST | `/post` | 멀티미디어 게시물 신규 등록 |
| GET | `/post/<id>` | 개별 게시물 상세 정보 조회 |
| PUT | `/post/<id>` | 게시물 내용 및 첨부 이미지 수정 |
| DELETE | `/post/<id>` | 게시물 삭제 (상태 값 변경) |
| GET | `/post` | 전체 게시물 목록 조회 (페이지네이션 적용) |
| POST | `/post/<id>/like` | 게시물 좋아요 등록 |
| DELETE | `/post/<id>/like` | 게시물 좋아요 취소 |
| GET | `/post/<id>/likes` | 좋아요를 누른 사용자 리스트 확인 |
| POST | `/reply` | 댓글 및 대댓글(계층형) 작성 |
| GET | `/reply/<id>` | 개별 댓글 상세 데이터 조회 |
| PUT | `/reply/<id>` | 작성한 댓글 내용 수정 |
| DELETE | `/reply/<id>` | 댓글 삭제 처리 (하위 구조 유지) |
| GET | `/reply/post/<id>` | 게시물에 달린 전체 댓글 목록 조회 |
| POST | `/reply/<id>/like` | 댓글 단위 좋아요 등록 |
| DELETE | `/reply/<id>/like` | 댓글 단위 좋아요 취소 |

🗺️ 위치 기반 경로 최적화 서비스

| **방식** | **엔드포인트** | **설명** |
| --- | --- | --- |
| POST | `/route/search` | OSRM 기반 최적 이동 경로 연산 |
| POST | `/route/save` | 연산된 추천 경로 데이터 저장 |
| GET | `/route/saved` | 사용자가 저장한 경로 아카이브 조회 |
| DELETE | `/route/<id>` | 저장된 경로 기록 삭제 |
| POST | `/place` | 관심 지점(POI) 데이터 신규 등록 |
| GET | `/place` | 저장된 장소 인덱스 전체 조회 |
| GET | `/place/<id>` | 특정 장소 상세 좌표 및 정보 조회 |
| PUT | `/place/<id>` | 장소 메타데이터 업데이트 |
| DELETE | `/place/<id>` | 저장된 장소 데이터 삭제 |

**🎨 프로필 커스터마이징**

| **방식** | **엔드포인트** | **설명** |
| --- | --- | --- |
| GET | `/cosmetic/items` | 프로필 꾸미기 아이템 전체 목록 조회 |
| GET | `/cosmetic/sets` | 아이템 세트(번들) 목록 조회 |
| GET | `/cosmetic/user/items` | 사용자가 보유한 아이템 인벤토리 |
| GET | `/cosmetic/user/state` | 현재 프로필에 장착된 아이템 상태 조회 |
| PUT | `/cosmetic/user/state` | 프로필 아이템 장착/해제 (보더, 오버레이, 테마, 폰트, 이펙트, 배지) |
| POST | `/cosmetic/purchase/<id>` | 포인트를 사용한 아이템 구매 |

**🛍️ 커머스 및 상품 관리**

| **방식** | **엔드포인트** | **설명** |
| --- | --- | --- |
| POST | `/product` | 상품 데이터 신규 등록 |
| GET | `/product` | 판매 중인 전체 상품 목록 조회 |
| GET | `/product/<id>` | 특정 상품 상세 정보 및 재고 확인 |
| PUT | `/product/<id>` | 상품 정보 및 상태 값 수정 |
| DELETE | `/product/<id>` | 상품 판매 중단 및 삭제 |

🔔 실시간 알림 서비스

| **방식** | **엔드포인트** | **설명** |
| --- | --- | --- |
| GET | `/notification` | 사용자별 수신된 전체 알림 목록 조회 |
| PUT | `/notification/<id>/read` | 특정 알림 읽음 상태로 업데이트 |
| DELETE | `/notification/<id>` | 특정 알림 레코드 삭제 |
| DELETE | `/notification/all` | 현재 사용자의 모든 알림 데이터 초기화 |

🖼️ 이미지 서버 및 스토리지 핸들러

| **방식** | **엔드포인트** | **설명** |
| --- | --- | --- |
| POST | `/image/upload` | 멀티파트 파일 업로드 및 고유 UUID 생성 |
| GET | `/image/profile/<uuid>` | 사용자 프로필 전용 이미지 서빙 |
| GET | `/image/post/<uuid>` | 게시물 첨부 미디어 데이터 조회 |
| GET | `/image/product/<uuid>` | 커머스 상품 상세 이미지 조회 |

⭐ 북마크 및 저장 관리

| **방식** | **엔드포인트** | **설명** |
| --- | --- | --- |
| GET | `/favorite` | 사용자가 저장한 전체 북마크 목록 (타입별 필터 가능) |
| GET | `/favorite/me/<type>` | 특정 타입의 저장 목록 상세 조회 (STORY, ROUTE, REVIEW, REPORT, PRODUCT, PLACE) |
| PATCH | `/favorite/<type>/<id>` | 북마크 토글 (저장/해제) |
| DELETE | `/favorite/<type>/<id>` | 특정 북마크 삭제 |
| GET | `/favorite/check/<type>/<id>` | 특정 컨텐츠의 저장 여부 확인 |

📺 피드 및 타임라인

| **방식** | **엔드포인트** | **설명** |
| --- | --- | --- |
| GET | `/feed` | 팔로우 기반 사용자 맞춤형 타임라인 조회 (본인 포함) |
| GET | `/feed/products` | 사용자 관심사 분석 기반 추천 상품 피드 추출 |
| GET | `/feed/combined` | 소셜 게시물과 커머스 상품이 결합된 통합 피드 제공 |

💳 결제 프로세스 및 이력 관리

| **방식** | **엔드포인트** | **설명** |
| --- | --- | --- |
| POST | `/payment/request` | 외부 결제 모듈 호출을 위한 세션 요청 |
| POST | `/payment/verify` | 결제 완료 데이터 검증 및 무결성 확인 |
| GET | `/payment/history` | 사용자별 과거 결제 및 거래 이력 조회 |

@ 사용자 멘션 및 태깅 시스템

| **방식** | **엔드포인트** | **설명** |
| --- | --- | --- |
| GET | `/mention` | 내가 멘션된 게시물 및 댓글 알림 피드 |
| GET | `/mention/post/<id>` | 특정 게시물 내에 포함된 멘션 유저 리스트 |

🚨 신고 센터 및 콘텐츠 중재

| **방식** | **엔드포인트** | **설명** |
| --- | --- | --- |
| POST | `/report` | 부적절한 게시물/사용자 신고 접수 |
| GET | `/report` | (관리자) 미처리 신고 접수 현황 조회 |
| PUT | `/report/<id>` | 신고 안건에 대한 처리 결과 업데이트 |

📷 현장 정보 로드뷰 서비스

| **방식** | **엔드포인트** | **설명** |
| --- | --- | --- |
| GET | `/roadview` | 특정 좌표 기준 현장 로드뷰 이미지 추출 |
| POST | `/roadview/upload` | 신규 지점에 대한 유저 참여형 로드뷰 업로드 |

👑 관리자 전용 관제 시스템

| **방식** | **엔드포인트** | **설명** |
| --- | --- | --- |
| GET | `/admin/users` | 전체 서비스 가입자 명단 관리 |
| PUT | `/admin/user/<id>/suspend` | 비정상 사용자 계정 활동 일시 정지 |
| PUT | `/admin/user/<id>/activate` | 정지된 계정 권한 복구 및 활성화 |
| GET | `/admin/reports` | 도메인별 신고 통계 및 리포트 관리 |
| GET | `/admin/statistics` | DAU, 매출액 등 서비스 핵심 지표 분석 |

🔍 통합 검색 엔진

| **방식** | **엔드포인트** | **설명** |
| --- | --- | --- |
| GET | `/search` | 유저/게시물/장소 통합 키워드 검색 |
| GET | `/search/history` | 사용자별 최근 검색어 기록 아카이브 |
| DELETE | `/search/history` | 개인 검색 히스토리 삭제 |
| GET | `/search/popular` | 실시간 트렌드 기반 인기 검색어 추출 |