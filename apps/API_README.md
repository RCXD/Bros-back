# Bros-back API 문서

## 목차
- [개요](#개요)
- [인증](#인증)
- [모듈별 API](#모듈별-api)
  - [인증 (Auth)](#인증-auth)
  - [사용자 (User)](#사용자-user)
  - [게시글 (Post)](#게시글-post)
  - [댓글 (Reply)](#댓글-reply)
  - [피드 (Feed)](#피드-feed)
  - [보안 (Security)](#보안-security)
  - [관리자 (Admin)](#관리자-admin)
  - [테스트 (Test)](#테스트-test)
- [에러 코드](#에러-코드)

---

## 개요

Bros-back은 소셜 네트워킹 기능을 갖춘 RESTful API 서버입니다.

**기술 스택:**
- Flask 2.x
- SQLAlchemy ORM
- Flask-JWT-Extended (JWT 인증)
- MySQL

**기본 URL:** `http://localhost:5000`

**응답 형식:** JSON

---

## 인증

### JWT 토큰 기반 인증

대부분의 API는 JWT 토큰이 필요합니다.

**헤더 형식:**
```
Authorization: Bearer <access_token>
```

**토큰 종류:**
- `access_token`: API 호출용 (유효기간: 1시간)
- `refresh_token`: 액세스 토큰 갱신용 (유효기간: 30일)

---

## 모듈별 API

### 인증 (Auth)

Base URL: `/auth`

#### 1. 회원가입
```
POST /auth/user
Content-Type: multipart/form-data
```

**요청 파라미터:**
| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| username | string | ✓ | 사용자명 (고유) |
| password | string | ✓ | 비밀번호 |
| email | string | ✓ | 이메일 (고유) |
| nickname | string | | 닉네임 |
| address | string | | 주소 |
| phone | string | | 전화번호 |
| profile_img | file | | 프로필 이미지 |

**응답 예시:**
```json
{
  "message": "회원가입이 완료되었습니다",
  "user": {
    "user_id": 1,
    "username": "john_doe",
    "email": "john@example.com",
    "nickname": "John",
    "created_at": "2025-11-14T10:00:00"
  }
}
```

**에러:**
- `400`: 필수 필드 누락, 유효하지 않은 이메일/전화번호
- `409`: 이미 존재하는 사용자명 또는 이메일

---

#### 2. 로그인
```
POST /auth/login
Content-Type: application/json
```

**요청 본문:**
```json
{
  "username": "john_doe",
  "password": "password123"
}
```

**응답 예시:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "user_id": 1,
    "username": "john_doe",
    "email": "john@example.com",
    "nickname": "John"
  }
}
```

**에러:**
- `400`: username과 password 필수
- `401`: 잘못된 인증 정보
- `403`: 정지된 계정

---

#### 3. 프로필 수정
```
PUT /auth/user
Authorization: Bearer <token>
Content-Type: multipart/form-data
```

**요청 파라미터 (모두 선택):**
- `email`: 새 이메일
- `password`: 새 비밀번호
- `nickname`: 새 닉네임
- `address`: 새 주소
- `phone`: 새 전화번호
- `profile_img`: 새 프로필 이미지

**응답:**
```json
{
  "message": "프로필이 성공적으로 업데이트되었습니다",
  "user": { ... }
}
```

---

#### 4. 로그아웃
```
DELETE /auth/logout
Authorization: Bearer <token>
```

**응답:**
```json
{
  "message": "로그아웃 성공"
}
```

---

#### 5. 토큰 갱신
```
POST /auth/refresh
Authorization: Bearer <refresh_token>
```

**응답:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

---

#### 6. 현재 사용자 정보
```
GET /auth/me
Authorization: Bearer <token>
```

**응답:**
```json
{
  "user_id": 1,
  "username": "john_doe",
  "email": "john@example.com",
  "nickname": "John",
  "address": "서울시 강남구",
  "profile_img": "apps/static/profile_images/user1.jpg",
  "follower_count": 150,
  "created_at": "2025-01-01T00:00:00"
}
```

---

#### 7. 계정 삭제
```
DELETE /auth/user
Authorization: Bearer <token>
```

**응답:**
```json
{
  "message": "계정이 삭제되었습니다"
}
```

---

### 사용자 (User)

Base URL: `/user`

#### 1. 사용자 프로필 조회
```
GET /user/<user_id>
```

**응답:**
```json
{
  "user_id": 2,
  "username": "jane_doe",
  "nickname": "Jane",
  "profile_img": "apps/static/profile_images/user2.jpg",
  "follower_count": 320,
  "created_at": "2025-01-15T10:30:00"
}
```

---

#### 2. 사용자 팔로우
```
POST /user/<user_id>/follow
Authorization: Bearer <token>
```

**응답:**
```json
{
  "message": "팔로우 성공"
}
```

**에러:**
- `400`: 자기 자신을 팔로우할 수 없음
- `409`: 이미 팔로우 중

---

#### 3. 사용자 언팔로우
```
DELETE /user/<user_id>/follow
Authorization: Bearer <token>
```

**응답:**
```json
{
  "message": "언팔로우 성공"
}
```

---

#### 4. 팔로워 목록
```
GET /user/<user_id>/followers
```

**응답:**
```json
{
  "followers": [
    {
      "user_id": 3,
      "username": "bob_smith",
      "nickname": "Bob",
      "profile_img": "..."
    }
  ],
  "count": 1
}
```

---

#### 5. 팔로잉 목록
```
GET /user/<user_id>/following
```

**응답:**
```json
{
  "following": [
    {
      "user_id": 4,
      "username": "alice_wonder",
      "nickname": "Alice",
      "profile_img": "..."
    }
  ],
  "count": 1
}
```

---

#### 6. 친구 추가
```
POST /user/<user_id>/friend
Authorization: Bearer <token>
```

**응답:**
```json
{
  "message": "친구 추가 성공"
}
```

**에러:**
- `400`: 자기 자신을 친구로 추가할 수 없음
- `409`: 이미 친구

---

#### 7. 친구 삭제
```
DELETE /user/<user_id>/friend
Authorization: Bearer <token>
```

**응답:**
```json
{
  "message": "친구 삭제 성공"
}
```

---

#### 8. 내 친구 목록
```
GET /user/me/friends
Authorization: Bearer <token>
```

**응답:**
```json
{
  "friends": [
    {
      "user_id": 5,
      "username": "charlie",
      "nickname": "Charlie",
      "profile_img": "...",
      "created_at": "2025-10-01T14:20:00"
    }
  ],
  "count": 1
}
```

---

### 게시글 (Post)

Base URL: `/post`

#### 1. 게시글 목록 조회
```
GET /post?page=1&per_page=20&category=여행&order_by=latest
```

**쿼리 파라미터:**
| 파라미터 | 타입 | 기본값 | 설명 |
|---------|------|--------|------|
| page | integer | 1 | 페이지 번호 |
| per_page | integer | 20 | 페이지당 항목 수 |
| category | string | | 카테고리 필터 |
| order_by | string | latest | 정렬 (latest/popular) |

**응답:**
```json
{
  "posts": [
    {
      "post_id": 1,
      "user_id": 1,
      "content": "안녕하세요, 첫 게시글입니다!",
      "category": "일상",
      "view_counts": 45,
      "like_count": 12,
      "created_at": "2025-11-14T09:00:00",
      "updated_at": "2025-11-14T09:00:00"
    }
  ],
  "total": 150,
  "pages": 8,
  "current_page": 1
}
```

---

#### 2. 게시글 작성
```
POST /post
Authorization: Bearer <token>
Content-Type: multipart/form-data
```

**요청 파라미터:**
| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| content | string | ✓ | 게시글 내용 |
| category_id | integer | ✓ | 카테고리 ID |
| images | file[] | | 이미지 파일들 |

**응답:**
```json
{
  "message": "게시글이 작성되었습니다",
  "post_id": 25
}
```

---

#### 3. 게시글 상세 조회
```
GET /post/<post_id>
```

**응답:**
```json
{
  "post_id": 1,
  "user_id": 1,
  "author": {
    "user_id": 1,
    "username": "john_doe",
    "nickname": "John",
    "profile_img": "..."
  },
  "content": "안녕하세요, 첫 게시글입니다!",
  "category": "일상",
  "view_counts": 46,
  "like_count": 12,
  "created_at": "2025-11-14T09:00:00",
  "updated_at": "2025-11-14T09:00:00"
}
```

---

#### 4. 게시글 수정
```
PUT /post/<post_id>
Authorization: Bearer <token>
Content-Type: multipart/form-data
```

**요청 파라미터:**
- `content`: 수정할 내용
- `images`: 수정할 이미지

**응답:**
```json
{
  "message": "게시글이 수정되었습니다"
}
```

**에러:**
- `403`: 권한이 없습니다 (작성자만 수정 가능)

---

#### 5. 게시글 삭제
```
DELETE /post/<post_id>
Authorization: Bearer <token>
```

**응답:**
```json
{
  "message": "게시글이 삭제되었습니다"
}
```

---

#### 6. 게시글 좋아요 (토글)
```
POST /post/<post_id>/like
Authorization: Bearer <token>
```

**응답:**
```json
{
  "message": "좋아요",
  "liked": true
}
```

또는

```json
{
  "message": "좋아요 취소",
  "liked": false
}
```

---

#### 7. 게시글 좋아요 취소
```
DELETE /post/<post_id>/like
Authorization: Bearer <token>
```

**응답:**
```json
{
  "message": "좋아요 취소"
}
```

---

#### 8. 게시글 좋아요 목록
```
GET /post/<post_id>/likes
```

**응답:**
```json
{
  "likes": [
    {
      "user_id": 2,
      "username": "jane_doe",
      "nickname": "Jane",
      "profile_img": "..."
    }
  ],
  "count": 1
}
```

---

#### 9. 내 게시글 목록
```
GET /post/me?page=1&per_page=20
Authorization: Bearer <token>
```

**응답:**
```json
{
  "posts": [ ... ],
  "total": 15,
  "pages": 1,
  "current_page": 1
}
```

---

### 댓글 (Reply)

Base URL: `/reply`

#### 1. 댓글 목록 조회
```
GET /reply?post_id=1&page=1&per_page=20
```

**쿼리 파라미터:**
| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| post_id | integer | ✓ | 게시글 ID |
| page | integer | | 페이지 번호 |
| per_page | integer | | 페이지당 항목 수 |

**응답:**
```json
{
  "replies": [
    {
      "reply_id": 1,
      "post_id": 1,
      "user_id": 2,
      "author": {
        "username": "jane_doe",
        "nickname": "Jane",
        "profile_img": "..."
      },
      "content": "좋은 글이네요!",
      "parent_id": null,
      "like_count": 5,
      "child_count": 2,
      "created_at": "2025-11-14T10:30:00",
      "updated_at": "2025-11-14T10:30:00"
    }
  ],
  "total": 10,
  "pages": 1,
  "current_page": 1
}
```

---

#### 2. 댓글 작성
```
POST /reply
Authorization: Bearer <token>
Content-Type: application/json
```

**요청 본문:**
```json
{
  "post_id": 1,
  "content": "좋은 글이네요!",
  "parent_id": null
}
```

**parent_id가 있으면 대댓글이 됩니다.**

**응답:**
```json
{
  "message": "댓글이 작성되었습니다",
  "reply_id": 15
}
```

---

#### 3. 댓글 상세 조회
```
GET /reply/<reply_id>
```

**응답:**
```json
{
  "reply_id": 1,
  "post_id": 1,
  "user_id": 2,
  "author": { ... },
  "content": "좋은 글이네요!",
  "parent_id": null,
  "like_count": 5,
  "created_at": "2025-11-14T10:30:00",
  "updated_at": "2025-11-14T10:30:00"
}
```

---

#### 4. 댓글 수정
```
PUT /reply/<reply_id>
Authorization: Bearer <token>
Content-Type: application/json
```

**요청 본문:**
```json
{
  "content": "수정된 댓글 내용"
}
```

**응답:**
```json
{
  "message": "댓글이 수정되었습니다"
}
```

---

#### 5. 댓글 삭제
```
DELETE /reply/<reply_id>
Authorization: Bearer <token>
```

**응답:**
```json
{
  "message": "댓글이 삭제되었습니다"
}
```

---

#### 6. 댓글 좋아요 (토글)
```
POST /reply/<reply_id>/like
Authorization: Bearer <token>
```

**응답:**
```json
{
  "message": "댓글 좋아요",
  "liked": true
}
```

---

#### 7. 댓글 좋아요 취소
```
DELETE /reply/<reply_id>/like
Authorization: Bearer <token>
```

**응답:**
```json
{
  "message": "댓글 좋아요 취소"
}
```

---

#### 8. 대댓글 조회
```
GET /reply/<reply_id>/replies
```

**응답:**
```json
{
  "replies": [
    {
      "reply_id": 2,
      "post_id": 1,
      "user_id": 3,
      "author": { ... },
      "content": "저도 동의합니다",
      "like_count": 2,
      "created_at": "2025-11-14T11:00:00",
      "updated_at": "2025-11-14T11:00:00"
    }
  ],
  "count": 1
}
```

---

### 피드 (Feed)

Base URL: `/feed`

#### 1. 개인화된 피드
```
GET /feed?page=1&per_page=20
Authorization: Bearer <token>
```

**설명:** 팔로우하는 사용자들의 게시글과 자신의 게시글을 시간순으로 표시합니다.

**응답:**
```json
{
  "posts": [
    {
      "post_id": 50,
      "author": {
        "user_id": 2,
        "username": "jane_doe",
        "nickname": "Jane",
        "profile_img": "..."
      },
      "content": "오늘 날씨가 좋네요!",
      "category": "일상",
      "view_counts": 23,
      "like_count": 7,
      "created_at": "2025-11-14T12:00:00"
    }
  ],
  "total": 45,
  "pages": 3,
  "current_page": 1
}
```

---

#### 2. 트렌딩 게시글
```
GET /feed/trending?period=week&limit=20
```

**쿼리 파라미터:**
| 파라미터 | 타입 | 기본값 | 설명 |
|---------|------|--------|------|
| period | string | week | 기간 (today/week/month) |
| limit | integer | 20 | 게시글 수 |

**응답:**
```json
{
  "posts": [
    {
      "post_id": 42,
      "author": {
        "user_id": 5,
        "username": "popular_user",
        "nickname": "인기유저"
      },
      "content": "이번 주 핫한 게시글...",
      "category": "트렌드",
      "view_counts": 1523,
      "like_count": 342,
      "created_at": "2025-11-10T15:30:00"
    }
  ],
  "count": 20
}
```

---

#### 3. 탐색 피드
```
GET /feed/explore?category=여행&page=1
```

**쿼리 파라미터:**
- `category`: 카테고리 필터
- `page`: 페이지 번호

**응답:**
```json
{
  "posts": [ ... ],
  "total": 200,
  "pages": 10,
  "current_page": 1
}
```

---

#### 4. 주변 게시글
```
GET /feed/nearby?lat=37.5665&lon=126.9780&radius=10
Authorization: Bearer <token>
```

**쿼리 파라미터:**
| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| lat | float | ✓ | 위도 |
| lon | float | ✓ | 경도 |
| radius | float | | 검색 반경(km) 기본값: 10 |

**응답:**
```json
{
  "posts": [],
  "message": "지리공간 검색이 아직 구현되지 않았습니다"
}
```

---

### 보안 (Security)

Base URL: `/security`

#### 1. 콘텐츠 신고
```
POST /security/reports
Authorization: Bearer <token>
Content-Type: application/json
```

**요청 본문:**
```json
{
  "target_type": "POST",
  "target_id": 15,
  "reason": "부적절한 콘텐츠"
}
```

**target_type:** USER, POST, REPLY 중 하나

**응답:**
```json
{
  "message": "신고가 제출되었습니다",
  "report_id": 7
}
```

**에러:**
- `400`: 필수 필드 누락, 유효하지 않은 target_type
- `409`: 이미 신고한 콘텐츠

---

#### 2. 내 신고 목록
```
GET /security/reports
Authorization: Bearer <token>
```

**응답:**
```json
{
  "reports": [
    {
      "report_id": 7,
      "target_type": "POST",
      "target_id": 15,
      "reason": "부적절한 콘텐츠",
      "is_resolved": false,
      "created_at": "2025-11-14T13:00:00",
      "resolved_at": null
    }
  ],
  "count": 1
}
```

---

#### 3. 신고 상세 조회
```
GET /security/reports/<report_id>
Authorization: Bearer <token>
```

**응답:**
```json
{
  "report_id": 7,
  "target_type": "POST",
  "target_id": 15,
  "reason": "부적절한 콘텐츠",
  "is_resolved": false,
  "created_at": "2025-11-14T13:00:00",
  "resolved_at": null
}
```

---

#### 4. 신고 취소
```
DELETE /security/reports/<report_id>
Authorization: Bearer <token>
```

**응답:**
```json
{
  "message": "신고가 취소되었습니다"
}
```

**에러:**
- `400`: 처리 완료된 신고는 취소할 수 없음
- `403`: 권한 없음

---

### 관리자 (Admin)

Base URL: `/admin`
**모든 엔드포인트는 관리자 권한 필요**

#### 1. 사용자 목록 조회
```
GET /admin/users?page=1&per_page=20&username=john
Authorization: Bearer <admin_token>
```

**쿼리 파라미터:**
- `username`: 사용자명 필터
- `email`: 이메일 필터
- `nickname`: 닉네임 필터
- `account_type`: 계정 유형 (USER/ADMIN)
- `page`: 페이지 번호
- `per_page`: 페이지당 항목 수

**응답:**
```json
{
  "users": [
    {
      "user_id": 1,
      "username": "john_doe",
      "nickname": "John",
      "email": "john@example.com",
      "address": "서울시 강남구",
      "profile_img": "...",
      "created_at": "2025-01-01T00:00:00",
      "last_login": "2025-11-14T08:00:00",
      "account_type": "USER",
      "oauth_type": "EMAIL",
      "follower_count": 150,
      "is_expired": false
    }
  ],
  "total": 500,
  "pages": 25,
  "current_page": 1,
  "per_page": 20
}
```

---

#### 2. 사용자 상세 정보
```
GET /admin/users/<user_id>
Authorization: Bearer <admin_token>
```

**응답:**
```json
{
  "user_id": 1,
  "username": "john_doe",
  "email": "john@example.com",
  ...
  "statistics": {
    "posts": 45,
    "replies": 123,
    "following": 50,
    "followers": 150
  }
}
```

---

#### 3. 사용자 정지
```
POST /admin/users/<user_id>/ban
Authorization: Bearer <admin_token>
Content-Type: application/json
```

**요청 본문 (선택):**
```json
{
  "reason": "규정 위반"
}
```

**응답:**
```json
{
  "message": "사용자 john_doe 계정이 정지되었습니다",
  "reason": "규정 위반"
}
```

**에러:**
- `400`: 관리자 계정은 정지할 수 없음

---

#### 4. 사용자 정지 해제
```
POST /admin/users/<user_id>/unban
Authorization: Bearer <admin_token>
```

**응답:**
```json
{
  "message": "사용자 john_doe 계정 정지가 해제되었습니다"
}
```

---

#### 5. 사용자 삭제
```
DELETE /admin/users/<user_id>
Authorization: Bearer <admin_token>
```

**응답:**
```json
{
  "message": "사용자 john_doe 삭제 완료"
}
```

**에러:**
- `400`: 관리자 계정은 삭제할 수 없음

---

#### 6. 플랫폼 통계
```
GET /admin/statistics
Authorization: Bearer <admin_token>
```

**응답:**
```json
{
  "users": {
    "total": 5000,
    "banned": 50,
    "admins": 5,
    "new_this_month": 150,
    "active_this_month": 3200
  },
  "content": {
    "total_posts": 12000,
    "total_replies": 45000,
    "posts_this_week": 320,
    "replies_this_week": 1150
  },
  "reports": {
    "total": 200,
    "pending": 25,
    "resolved": 175
  }
}
```

---

#### 7. 일별 활동 통계
```
GET /admin/statistics/activity?days=30
Authorization: Bearer <admin_token>
```

**응답:**
```json
{
  "user_registrations": [
    {"date": "2025-11-14", "count": 15},
    {"date": "2025-11-13", "count": 22}
  ],
  "posts": [
    {"date": "2025-11-14", "count": 45},
    {"date": "2025-11-13", "count": 52}
  ]
}
```

---

#### 8. 신고 목록
```
GET /admin/reports?status=pending&page=1
Authorization: Bearer <admin_token>
```

**쿼리 파라미터:**
- `status`: pending/resolved
- `page`: 페이지 번호
- `per_page`: 페이지당 항목 수

**응답:**
```json
{
  "reports": [
    {
      "report_id": 1,
      "reporter_id": 5,
      "target_type": "POST",
      "target_id": 100,
      "reason": "스팸",
      "created_at": "2025-11-14T10:00:00",
      "is_resolved": false,
      "resolved_at": null
    }
  ],
  "total": 25,
  "pages": 2,
  "current_page": 1
}
```

---

#### 9. 신고 처리
```
POST /admin/reports/<report_id>/resolve
Authorization: Bearer <admin_token>
```

**응답:**
```json
{
  "message": "신고가 처리되었습니다"
}
```

---

### 테스트 (Test)

Base URL: `/test`

#### 1. 헬스 체크
```
GET /test/health
```

**응답:**
```json
{
  "status": "ok",
  "message": "서비스 정상 작동 중",
  "environment": "development"
}
```

---

#### 2. 데이터베이스 테스트
```
GET /test/db
```

**응답:**
```json
{
  "status": "ok",
  "database": "연결됨",
  "stats": {
    "users": 5000,
    "posts": 12000
  }
}
```

---

#### 3. 설정 조회
```
GET /test/config
```

**응답:**
```json
{
  "environment": "development",
  "debug": true,
  "testing": false,
  "database_type": "mysql",
  "jwt_enabled": true,
  "cors_enabled": true
}
```

---

#### 4. 에러 시뮬레이션
```
POST /test/error?code=400
```

**응답:**
```json
{
  "error": "잘못된 요청 테스트",
  "test": true
}
```

---

## 에러 코드

### HTTP 상태 코드

| 코드 | 의미 | 설명 |
|------|------|------|
| 200 | OK | 요청 성공 |
| 201 | Created | 리소스 생성 성공 |
| 400 | Bad Request | 잘못된 요청 (필수 필드 누락, 유효하지 않은 데이터) |
| 401 | Unauthorized | 인증 실패 (토큰 없음, 잘못된 토큰) |
| 403 | Forbidden | 권한 없음 (접근 금지, 관리자 권한 필요) |
| 404 | Not Found | 리소스를 찾을 수 없음 |
| 409 | Conflict | 리소스 충돌 (중복된 데이터) |
| 500 | Internal Server Error | 서버 내부 오류 |
| 501 | Not Implemented | 구현되지 않은 기능 |

### 에러 응답 형식

```json
{
  "error": "에러 메시지"
}
```

---

## 페이지네이션

목록 API는 페이지네이션을 지원합니다.

**요청 파라미터:**
- `page`: 페이지 번호 (기본값: 1)
- `per_page`: 페이지당 항목 수 (기본값: 20)

**응답 형식:**
```json
{
  "items": [...],
  "total": 150,
  "pages": 8,
  "current_page": 1
}
```

---

## 개발 가이드

### 로컬 개발 환경 설정

1. **가상환경 생성 및 활성화**
```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
```

2. **의존성 설치**
```bash
pip install -r requirements.txt
```

3. **데이터베이스 마이그레이션**
```bash
flask db upgrade
```

4. **서버 실행**
```bash
python apps/app.py
```

### API 테스트

**Postman 또는 cURL 사용:**

```bash
# 회원가입
curl -X POST http://localhost:5000/auth/user \
  -F "username=testuser" \
  -F "password=test123" \
  -F "email=test@example.com"

# 로그인
curl -X POST http://localhost:5000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"test123"}'

# 인증이 필요한 API 호출
curl -X GET http://localhost:5000/auth/me \
  -H "Authorization: Bearer <access_token>"
```

---

## 추가 정보

### 미구현 기능 (향후 구현 예정)

1. **OAuth 로그인**
   - Google, Kakao, Naver 로그인 통합

2. **이미지 업로드**
   - 프로필 이미지 및 게시글 이미지 업로드 기능

3. **경로 탐색 (Route)**
   - OSRM 통합 내비게이션 기능

4. **AI 감지 (Detector)**
   - 객체 감지 및 이미지 분석

5. **상품 리뷰 (Product)**
   - 상품 및 리뷰 시스템

6. **즐겨찾기 (Favorite)**
   - 게시글 북마크 기능

7. **사고 신고 (Accident Report)**
   - 도로 사고 및 위험 요소 신고

### 연락처

문의사항이 있으시면 개발팀에 문의해주세요.

---

**문서 버전:** 1.0  
**최종 업데이트:** 2025-11-14
