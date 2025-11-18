# API Documentation

Base URL: `http://localhost:8002`

## Authentication (인증)

| Method | Endpoint | Auth | Description | Request Body | Response |
|--------|----------|------|-------------|--------------|----------|
| POST | `/auth/user` | No | 회원가입 | Form: username, password, email, nickname?, address?, phone?, profile_img? | 201: user object |
| POST | `/auth/login` | No | 로그인 | JSON: username, password | 200: tokens + user object |
| POST | `/auth/login/google` | No | Google OAuth 로그인 | JSON: token | 200: tokens + user object |
| POST | `/auth/login/kakao` | No | Kakao OAuth 로그인 | JSON: token | 200: tokens + user object |
| POST | `/auth/login/naver` | No | Naver OAuth 로그인 | JSON: token | 200: tokens + user object |
| GET | `/auth/me` | Yes | 현재 사용자 정보 조회 | - | 200: user object |
| PUT | `/auth/user` | Yes | 프로필 수정 | Form: email?, password?, nickname?, address?, phone?, profile_img? | 200: user object |
| DELETE | `/auth/user` | Yes | 계정 삭제 | - | 200: success message |
| DELETE | `/auth/logout` | Yes | 로그아웃 | - | 200: success message |
| POST | `/auth/refresh` | Yes (Refresh) | 액세스 토큰 갱신 | - | 200: new access token |
| GET | `/auth/image/<uuid>` | No | 프로필 이미지 조회 | - | 200: image file |

## Posts (게시글)

| Method | Endpoint | Auth | Description | Query/Body Params | Response |
|--------|----------|------|-------------|-------------------|----------|
| GET | `/post` | No | 게시글 목록 조회 | Query: page?, per_page?, category?, order_by? | 200: paginated posts |
| POST | `/post` | Yes | 게시글 작성 | Form: content, category_id, images? | 201: post object + uploaded_images |
| GET | `/post/<post_id>` | No | 게시글 상세 조회 | - | 200: post object + author info |
| PUT | `/post/<post_id>` | Yes | 게시글 수정 | Form: content?, images?, delete_image_ids? | 200: post object + deleted/uploaded images |
| DELETE | `/post/<post_id>` | Yes | 게시글 삭제 | - | 200: success message |
| GET | `/post/me` | Yes | 내 게시글 조회 | Query: page?, per_page? | 200: paginated posts |
| POST | `/post/<post_id>/like` | Yes | 게시글 좋아요/취소 (토글) | - | 200/201: liked status + count |
| DELETE | `/post/<post_id>/like` | Yes | 게시글 좋아요 취소 | - | 200: success message |
| GET | `/post/<post_id>/likes` | No | 게시글 좋아요한 사용자 목록 | - | 200: user list + count |
| GET | `/post/image/<uuid>` | No | 게시글 이미지 조회 | - | 200: image file |

## Replies (댓글)

| Method | Endpoint | Auth | Description | Query/Body Params | Response |
|--------|----------|------|-------------|-------------------|----------|
| GET | `/reply` | No | 댓글 목록 조회 | Query: post_id?, parent_id?, page?, per_page? | 200: paginated replies |
| POST | `/reply` | Yes | 댓글 작성 | JSON: post_id, content, parent_id?, mention_user_ids? | 201: reply object |
| GET | `/reply/<reply_id>` | No | 댓글 상세 조회 | - | 200: reply object + author info |
| PUT | `/reply/<reply_id>` | Yes | 댓글 수정 | JSON: content | 200: reply object |
| DELETE | `/reply/<reply_id>` | Yes | 댓글 삭제 | - | 200: success message |
| GET | `/reply/<reply_id>/replies` | No | 대댓글 목록 조회 | Query: page?, per_page? | 200: paginated replies |
| POST | `/reply/<reply_id>/like` | Yes | 댓글 좋아요/취소 (토글) | - | 200/201: liked status + count |
| DELETE | `/reply/<reply_id>/like` | Yes | 댓글 좋아요 취소 | - | 200: success message |

## Users (사용자)

| Method | Endpoint | Auth | Description | Query/Body Params | Response |
|--------|----------|------|-------------|-------------------|----------|
| GET | `/user/<user_id>` | No | 사용자 프로필 조회 | - | 200: user object + stats |
| POST | `/user/<user_id>/follow` | Yes | 사용자 팔로우 | - | 201: success message |
| DELETE | `/user/<user_id>/follow` | Yes | 사용자 언팔로우 | - | 200: success message |
| GET | `/user/<user_id>/followers` | No | 팔로워 목록 조회 | Query: page?, per_page? | 200: paginated users |
| GET | `/user/<user_id>/following` | No | 팔로잉 목록 조회 | Query: page?, per_page? | 200: paginated users |
| POST | `/user/<user_id>/friend` | Yes | 친구 추가 | - | 201: success message |
| DELETE | `/user/<user_id>/friend` | Yes | 친구 삭제 | - | 200: success message |
| GET | `/user/me/friends` | Yes | 내 친구 목록 조회 | Query: page?, per_page? | 200: paginated friends |

## Notifications (알림)

| Method | Endpoint | Auth | Description | Query/Body Params | Response |
|--------|----------|------|-------------|-------------------|----------|
| POST | `/notification` | Yes | 알림 생성 (수동) | JSON: to_user_id, type, post_id?, reply_id?, mention_id?, product_id? | 201: notification object |
| GET | `/notification/me` | Yes | 내 알림 목록 조회 | Query: page?, per_page?, unread_only? | 200: paginated notifications |
| GET | `/notification/unread-count` | Yes | 읽지 않은 알림 개수 | - | 200: unread_count |
| PATCH | `/notification/<notification_id>` | Yes | 알림 읽음 처리 | - | 200: notification object |
| PATCH | `/notification/mark-all-read` | Yes | 모든 알림 읽음 처리 | - | 200: updated_count |
| DELETE | `/notification/<notification_id>` | Yes | 알림 삭제 | - | 200: success message |

## Favorites (즐겨찾기)

| Method | Endpoint | Auth | Description | Query/Body Params | Response |
|--------|----------|------|-------------|-------------------|----------|
| GET | `/favorite` | Yes | 즐겨찾기 목록 조회 | Query: item_type?, page?, per_page? | 200: paginated favorites |
| POST | `/favorite/<item_type>/<item_id>` | Yes | 즐겨찾기 추가 | - | 201: favorite object |
| DELETE | `/favorite/<item_type>/<item_id>` | Yes | 즐겨찾기 제거 | - | 200: success message |
| GET | `/favorite/check/<item_type>/<item_id>` | Yes | 즐겨찾기 여부 확인 | - | 200: is_favorited boolean |

**item_type**: story, route, review, report, product

## Feed (피드)

| Method | Endpoint | Auth | Description | Query Params | Response |
|--------|----------|------|-------------|--------------|----------|
| GET | `/feed` | Yes | 개인화 피드 조회 | Query: page?, per_page? | 200: paginated feed items |
| GET | `/feed/trending` | No | 트렌딩 게시글 조회 | Query: page?, per_page?, category? | 200: paginated posts |
| GET | `/feed/explore` | No | 탐색 피드 조회 | Query: page?, per_page?, category? | 200: paginated posts |
| GET | `/feed/nearby` | Yes | 근처 게시글 조회 | Query: latitude, longitude, radius?, page?, per_page? | 200: paginated posts with distance |

## Security (신고/사고)

| Method | Endpoint | Auth | Description | Request Body | Response |
|--------|----------|------|-------------|--------------|----------|
| POST | `/security/reports` | Yes | 신고 제출 | JSON: report_target_type, report_target_id, report_reason | 201: report object |
| GET | `/security/reports` | Yes | 내 신고 목록 조회 | Query: page?, per_page? | 200: paginated reports |
| GET | `/security/reports/<report_id>` | Yes | 신고 상세 조회 | - | 200: report object |
| DELETE | `/security/reports/<report_id>` | Yes | 신고 취소 | - | 200: success message |
| POST | `/security/accidents` | Yes | 사고 신고 | JSON: location_id, severity, description | 201: accident object |
| GET | `/security/accidents` | No | 사고 목록 조회 | Query: page?, per_page? | 200: paginated accidents |
| GET | `/security/accidents/<accident_id>` | No | 사고 상세 조회 | - | 200: accident object |
| PUT | `/security/accidents/<accident_id>` | Yes | 사고 정보 수정 | JSON: severity?, description? | 200: accident object |
| DELETE | `/security/accidents/<accident_id>` | Yes | 사고 신고 삭제 | - | 200: success message |

## Admin (관리자)

| Method | Endpoint | Auth | Description | Query/Body Params | Response |
|--------|----------|------|-------------|-------------------|----------|
| GET | `/admin/users` | Admin | 사용자 목록 조회 | Query: page?, per_page?, search?, filter? | 200: paginated users |
| GET | `/admin/users/<user_id>` | Admin | 사용자 상세 조회 | - | 200: user object + activity stats |
| POST | `/admin/users/<user_id>/ban` | Admin | 사용자 정지 | JSON: reason?, duration? | 200: success message |
| POST | `/admin/users/<user_id>/unban` | Admin | 사용자 정지 해제 | - | 200: success message |
| DELETE | `/admin/users/<user_id>` | Admin | 사용자 삭제 | - | 200: success message |
| GET | `/admin/statistics` | Admin | 전체 통계 조회 | - | 200: statistics object |
| GET | `/admin/statistics/activity` | Admin | 활동 통계 조회 | Query: start_date?, end_date? | 200: activity stats |
| GET | `/admin/reports` | Admin | 모든 신고 목록 조회 | Query: page?, per_page?, status? | 200: paginated reports |
| POST | `/admin/reports/<report_id>/resolve` | Admin | 신고 처리 | JSON: result, action? | 200: report object |
| GET | `/admin/image/user/<user_identifier>` | Admin | 사용자 이미지 조회 | - | 200: image file |

## Route (경로/위험요소)

| Method | Endpoint | Auth | Description | Request Body | Response |
|--------|----------|------|-------------|--------------|----------|
| POST | `/route/hazards` | Yes | 위험요소 등록 | JSON: location, hazard_type, severity, description | 201: hazard object |
| GET | `/route/hazard/active` | No | 활성 위험요소 조회 | Query: latitude?, longitude?, radius? | 200: hazards list |
| POST | `/route/hazard/refresh` | No | 위험요소 데이터 갱신 | - | 200: success message |
| POST | `/route/hazard/map-osm-edges` | No | OSM 엣지 매핑 | JSON: edges data | 200: mapping result |

## Products (제품)

| Method | Endpoint | Auth | Description | Query/Body Params | Response |
|--------|----------|------|-------------|-------------------|----------|
| GET | `/product` | No | 제품 목록 조회 | Query: category?, search?, page? | 200: paginated products |
| POST | `/product` | Admin | 제품 등록 | JSON: name, description, category, price? | 201: product object |
| GET | `/product/<product_id>` | No | 제품 상세 조회 | - | 200: product object + reviews |
| PUT | `/product/<product_id>` | Admin | 제품 정보 수정 | JSON: name?, description?, price? | 200: product object |
| DELETE | `/product/<product_id>` | Admin | 제품 삭제 | - | 200: success message |
| GET | `/product/<product_id>/reviews` | No | 제품 리뷰 목록 조회 | Query: page?, per_page? | 200: paginated reviews |
| POST | `/product/<product_id>/reviews` | Yes | 제품 리뷰 작성 | JSON: rating, content, images? | 201: review object |
| PUT | `/product/<product_id>/reviews/<review_id>` | Yes | 리뷰 수정 | JSON: rating?, content? | 200: review object |
| DELETE | `/product/<product_id>/reviews/<review_id>` | Yes | 리뷰 삭제 | - | 200: success message |

---

## Common Response Formats

### Success Response
```json
{
  "success": true,
  "data": { ... },
  "message": "Success message"
}
```

### Error Response
```json
{
  "success": false,
  "message": "Error message",
  "error": "Detailed error information"
}
```

### Pagination Response
```json
{
  "items": [ ... ],
  "total": 100,
  "page": 1,
  "per_page": 20,
  "pages": 5
}
```

## Authentication

대부분의 엔드포인트는 JWT 토큰 인증이 필요합니다.

**Header Format:**
```
Authorization: Bearer <access_token>
```

**Token Refresh:**
- Access Token 만료 시 `/auth/refresh` 엔드포인트를 사용하여 갱신
- Refresh Token을 Header에 포함하여 요청

## Notification Types

- `POST_LIKE`: 게시글 좋아요
- `FRIEND_REQUEST`: 친구 요청
- `REPLY`: 댓글 작성
- `REPLY_TO_REPLY`: 대댓글 작성
- `PRODUCT_RECOMMENDATION`: 제품 추천
- `MENTION`: 멘션
- `REPLY_LIKE`: 댓글 좋아요
- `FOLLOW`: 팔로우

## Report Target Types

- `post`: 게시글 신고
- `reply`: 댓글 신고
- `user`: 사용자 신고

## Favorite Item Types

- `story`: 스토리 게시글
- `route`: 경로 게시글
- `review`: 리뷰
- `report`: 신고
- `product`: 제품

## HTTP Status Codes

- `200`: 성공
- `201`: 생성 성공
- `400`: 잘못된 요청
- `401`: 인증 실패
- `403`: 권한 없음
- `404`: 리소스 없음
- `409`: 충돌 (중복 등)
- `500`: 서버 오류
- `501`: 미구현
