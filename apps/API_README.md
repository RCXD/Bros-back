# API Documentation

> **최종 업데이트**: 2025-11-19  
> **Base URL**: `http://192.168.1.86:8002`  
> **인증 방식**: JWT (Bearer Token)

이 문서는 모든 API 엔드포인트의 상세 스펙을 포함합니다. 요청/응답 객체의 모든 필드를 명시합니다.

---

## 목차
1. [인증 (Auth)](#1-인증-auth)
2. [사용자 (User)](#2-사용자-user)
3. [게시글 (Post)](#3-게시글-post)
4. [댓글 (Reply)](#4-댓글-reply)
5. [알림 (Notification)](#5-알림-notification)
6. [멘션 (Mention)](#6-멘션-mention)
7. [즐겨찾기 (Favorite)](#7-즐겨찾기-favorite)
8. [피드 (Feed)](#8-피드-feed)
9. [제품 (Product)](#9-제품-product)
10. [신고 (Report)](#10-신고-report)
11. [관리자 (Admin)](#11-관리자-admin)
12. [경로 (Route)](#12-경로-route)
13. [장소 (Place)](#13-장소-place)
14. [코스메틱 (Cosmetic)](#14-코스메틱-cosmetic)

---

## 1. 인증 (Auth)

Base Path: `/auth`

### 1.1 회원가입

**Endpoint**: `POST /auth/user`  
**인증**: 불필요  
**Content-Type**: `multipart/form-data`

**요청 (Form Data)**:
```
username: string (필수) - 사용자명
password: string (필수) - 비밀번호
email: string (필수) - 이메일
nickname: string (선택) - 닉네임 (기본값: username)
address: string (선택) - 주소
phone: string (선택) - 전화번호 (형식: 010-1234-5678)
profile_img: file (선택) - 프로필 이미지 파일
```

**응답 201 (성공)**:
```json
{
  "message": "회원가입이 완료되었습니다",
  "user": {
    "user_id": 1
  }
}
```

**응답 400 (실패)**:
```json
{
  "message": "username, password, email은 필수입니다"
}
// 또는
{
  "message": "유효하지 않은 이메일 형식입니다"
}
// 또는
{
  "message": "유효하지 않은 전화번호 형식입니다"
}
// 또는
{
  "message": "지원하지 않는 파일 형식: filename.txt"
}
```

**응답 409 (중복)**:
```json
{
  "message": "이미 존재하는 사용자명입니다"
}
// 또는
{
  "message": "이미 존재하는 이메일입니다"
}
```

---

### 1.2 통합 로그인

**Endpoint**: `POST /auth/login`  
**인증**: 불필요  
**Content-Type**: `application/json`

**요청 (일반 로그인)**:
```json
{
  "username": "testuser",
  "password": "password123"
}
```

**요청 (OAuth 로그인)**:
```json
{
  "provider": "google",  // "google", "kakao", "naver"
  "token": "oauth_access_token_here"
}
```

**응답 200 (성공)**:
```json
{
  "message": "로그인 성공",
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "csrf_access_token": "csrf_token_here",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "csrf_refresh_token": "csrf_refresh_token_here",
  "user_data": {
    "user_id": 1,
    "username": "testuser",
    "email": "test@example.com",
    "nickname": "테스트유저",
    "profile_img": "uuid-string-here",
    "address": "서울시 강남구",
    "phone": "010-1234-5678",
    "account_type": "USER",  // "USER", "ADMIN"
    "oauth_type": "NONE",  // "NONE", "GOOGLE", "KAKAO", "NAVER"
    "is_expired": false,
    "created_at": "2025-11-19T10:00:00",
    "last_login": "2025-11-19T13:00:00"
  }
}
```

**응답 400 (잘못된 요청)**:
```json
{
  "message": "username과 password는 필수입니다"
}
// 또는
{
  "message": "토큰이 누락되었습니다"
}
```

**응답 401 (인증 실패)**:
```json
{
  "message": "잘못된 인증 정보입니다"
}
// 또는
{
  "message": "유효하지 않은 토큰입니다"
}
// 또는
{
  "message": "토큰에서 필요한 정보를 가져올 수 없습니다"
}
```

**응답 403 (계정 정지)**:
```json
{
  "message": "정지된 계정입니다"
}
```

---

### 1.3 OAuth 로그인 (Deprecated)

**Endpoints**:
- `POST /auth/login/google`
- `POST /auth/login/kakao`
- `POST /auth/login/naver`

**인증**: 불필요  
**참고**: 통합 로그인 엔드포인트(`POST /auth/login`) 사용 권장

**요청**:
```json
{
  "token": "oauth_access_token"
}
```

**응답**: 1.2 통합 로그인과 동일

---

### 1.4 토큰 갱신

**Endpoint**: `POST /auth/refresh`  
**인증**: Refresh Token 필요  
**Content-Type**: `application/json`

**요청 헤더**:
```
Authorization: Bearer <refresh_token>
```

**응답 200 (성공)**:
```json
{
  "message": "로그인 성공",
  "access_token": "new_access_token_here",
  "csrf_access_token": "new_csrf_token_here",
  "user_data": {
    // User 객체 (1.2 참고)
  }
}
```

---

### 1.5 로그아웃

**Endpoint**: `DELETE /auth/logout`  
**인증**: 필요 (Access Token)

**요청 헤더**:
```
Authorization: Bearer <access_token>
```

**응답 200 (성공)**:
```json
{
  "message": "로그아웃 성공"
}
```

---

### 1.6 현재 사용자 정보 조회

**Endpoint**: `GET /auth/me`  
**인증**: 필요

**응답 200 (성공)**:
```json
{
  "user_id": 1,
  "username": "testuser",
  "email": "test@example.com",
  "nickname": "테스트유저",
  "profile_img": "uuid-string-here",
  "address": "서울시 강남구",
  "phone": "010-1234-5678",
  "account_type": "USER",
  "oauth_type": "NONE",
  "is_expired": false,
  "created_at": "2025-11-19T10:00:00",
  "last_login": "2025-11-19T13:00:00"
}
```

**응답 404**:
```json
{
  "message": "사용자를 찾을 수 없습니다"
}
```

---

### 1.7 프로필 수정

**Endpoint**: `PUT /auth/user`  
**인증**: 필요  
**Content-Type**: `multipart/form-data`

**요청 (Form Data, 모두 선택)**:
```
email: string - 새 이메일
password: string - 새 비밀번호
nickname: string - 새 닉네임
address: string - 새 주소
phone: string - 새 전화번호
profile_img: file - 새 프로필 이미지
```

**응답 200 (성공)**:
```json
{
  "message": "프로필이 성공적으로 업데이트되었습니다",
  "user": {
    // User 객체 (1.6 참고)
  }
}
```

**응답 400/409**: 회원가입과 동일한 검증 에러

---

### 1.8 계정 삭제

**Endpoint**: `DELETE /auth/user`  
**인증**: 필요

**응답 200 (성공)**:
```json
{
  "message": "계정이 삭제되었습니다"
}
```

---

### 1.9 프로필 이미지 조회

**Endpoint**: `GET /auth/image/<identifier>`  
**인증**: 불필요  
**Parameters**:
- `identifier`: 이미지 UUID, 또는 `default_profile`

**응답 200**: 이미지 파일 (binary)  
**응답 404**:
```json
{
  "message": "이미지 없음"
}
// 또는
{
  "message": "파일 없음: /path/to/file"
}
```

---

## 2. 사용자 (User)

Base Path: `/user`

### 2.1 팔로우

**Endpoint**: `POST /user/<user_id>/follow`  
**인증**: 필요

**응답 200 (성공)**:
```json
{
  "message": "팔로우했습니다",
  "is_following": true
}
```

**응답 400**:
```json
{
  "message": "자기 자신을 팔로우할 수 없습니다"
}
```

**응답 404**:
```json
{
  "message": "사용자를 찾을 수 없습니다"
}
```

---

### 2.2 언팔로우

**Endpoint**: `DELETE /user/<user_id>/follow`  
**인증**: 필요

**응답 200 (성공)**:
```json
{
  "message": "언팔로우했습니다",
  "is_following": false
}
```

---

### 2.3 팔로워 목록

**Endpoint**: `GET /user/<user_id>/followers`  
**인증**: 필요  
**Query Parameters**:
- `page`: integer (기본값: 1)
- `per_page`: integer (기본값: 20)

**응답 200**:
```json
{
  "items": [
    {
      "user_id": 2,
      "username": "follower1",
      "nickname": "팔로워1",
      "profile_img": "uuid-here",
      "created_at": "2025-11-19T10:00:00"
    }
  ],
  "total": 100,
  "pages": 5,
  "page": 1,
  "per_page": 20,
  "has_next": true,
  "has_prev": false
}
```

---

### 2.4 팔로잉 목록

**Endpoint**: `GET /user/<user_id>/following`  
**인증**: 필요  
**Query Parameters**: 2.3과 동일

**응답 200**: 2.3과 동일한 구조

---

### 2.5 친구 요청

**Endpoint**: `POST /user/<user_id>/friend`  
**인증**: 필요

**응답 200 (성공)**:
```json
{
  "message": "친구 요청을 보냈습니다"
}
```

**응답 400**:
```json
{
  "message": "자기 자신에게 친구 요청을 보낼 수 없습니다"
}
// 또는
{
  "message": "이미 친구 요청을 보냈습니다"
}
// 또는
{
  "message": "이미 친구입니다"
}
```

---

### 2.6 친구 요청 수락

**Endpoint**: `PUT /user/friend/<friend_id>/accept`  
**인증**: 필요

**응답 200 (성공)**:
```json
{
  "message": "친구 요청을 수락했습니다"
}
```

**응답 404**:
```json
{
  "message": "친구 요청을 찾을 수 없습니다"
}
```

---

### 2.7 친구 요청 거절/삭제

**Endpoint**: `DELETE /user/friend/<friend_id>`  
**인증**: 필요

**응답 200 (성공)**:
```json
{
  "message": "친구 관계가 삭제되었습니다"
}
```

---

### 2.8 친구 목록

**Endpoint**: `GET /user/friends`  
**인증**: 필요  
**Query Parameters**:
- `page`: integer (기본값: 1)
- `per_page`: integer (기본값: 20)
- `status`: string (선택) - `"pending"`, `"accepted"`

**응답 200**:
```json
{
  "items": [
    {
      "friend_id": 1,
      "user_id": 2,
      "friend_user_id": 3,
      "status": "accepted",  // "pending", "accepted"
      "created_at": "2025-11-19T10:00:00",
      "user": {
        "user_id": 3,
        "username": "friend1",
        "nickname": "친구1",
        "profile_img": "uuid-here"
      }
    }
  ],
  "total": 50,
  "pages": 3,
  "page": 1,
  "per_page": 20,
  "has_next": true,
  "has_prev": false
}
```

---

## 3. 게시글 (Post)

Base Path: `/post`

### 3.1 게시글 목록 조회

**Endpoint**: `GET /post`  
**인증**: 불필요  
**Query Parameters**:
- `page`: integer (기본값: 1)
- `per_page`: integer (기본값: 20)
- `category`: string (선택) - 카테고리 필터
- `user_id`: integer (선택) - 특정 사용자의 게시글만

**응답 200**:
```json
{
  "items": [
    {
      "post_id": 1,
      "user_id": 1,
      "author": {
        "user_id": 1,
        "username": "testuser",
        "nickname": "테스트",
        "profile_img": "uuid-here"
      },
      "title": "게시글 제목",
      "content": "게시글 내용",
      "category": "FREE",  // "FREE", "NOTICE", "QNA" 등
      "view_count": 100,
      "like_count": 10,
      "reply_count": 5,
      "images": [
        {
          "uuid": "image-uuid-1",
          "original_image_name": "photo.jpg",
          "directory": "static/post_images/2025-11-19/uuid.jpg"
        }
      ],
      "created_at": "2025-11-19T10:00:00",
      "updated_at": "2025-11-19T11:00:00"
    }
  ],
  "total": 150,
  "pages": 8,
  "page": 1,
  "per_page": 20,
  "has_next": true,
  "has_prev": false
}
```

---

### 3.2 게시글 작성

**Endpoint**: `POST /post`  
**인증**: 필요  
**Content-Type**: `multipart/form-data`

**요청 (Form Data)**:
```
title: string (필수) - 제목
content: string (필수) - 내용
category: string (선택) - 카테고리 (기본값: "FREE")
images: file[] (선택) - 이미지 파일들 (multiple)
```

**응답 201 (성공)**:
```json
{
  "message": "게시글이 생성되었습니다",
  "post": {
    // Post 객체 (3.1 참고)
  }
}
```

**응답 400**:
```json
{
  "message": "제목과 내용은 필수입니다"
}
```

---

### 3.3 게시글 상세 조회

**Endpoint**: `GET /post/<post_id>`  
**인증**: 불필요

**응답 200**:
```json
{
  "post_id": 1,
  "user_id": 1,
  "author": {
    "user_id": 1,
    "username": "testuser",
    "nickname": "테스트",
    "profile_img": "uuid-here"
  },
  "title": "게시글 제목",
  "content": "게시글 내용",
  "category": "FREE",
  "view_count": 101,  // 조회 시 +1
  "like_count": 10,
  "reply_count": 5,
  "images": [
    // Image 객체들 (3.1 참고)
  ],
  "created_at": "2025-11-19T10:00:00",
  "updated_at": "2025-11-19T11:00:00"
}
```

**응답 404**:
```json
{
  "message": "게시글을 찾을 수 없습니다"
}
```

---

### 3.4 게시글 수정

**Endpoint**: `PUT /post/<post_id>`  
**인증**: 필요 (작성자만)  
**Content-Type**: `multipart/form-data`

**요청 (Form Data, 모두 선택)**:
```
title: string - 새 제목
content: string - 새 내용
category: string - 새 카테고리
images: file[] - 추가할 이미지들
delete_image_ids: string - 삭제할 이미지 UUID (쉼표로 구분)
```

**응답 200 (성공)**:
```json
{
  "message": "게시글이 수정되었습니다",
  "post": {
    // Post 객체 (3.1 참고)
  },
  "deleted_images": [
    {
      "uuid": "deleted-uuid-1",
      "original_image_name": "old_photo.jpg"
    }
  ]
}
```

**응답 403**:
```json
{
  "message": "게시글을 수정할 권한이 없습니다"
}
```

---

### 3.5 게시글 삭제

**Endpoint**: `DELETE /post/<post_id>`  
**인증**: 필요 (작성자 또는 관리자)

**응답 200 (성공)**:
```json
{
  "message": "게시글이 삭제되었습니다"
}
```

**응답 403**:
```json
{
  "message": "게시글을 삭제할 권한이 없습니다"
}
```

---

### 3.6 게시글 좋아요

**Endpoint**: `POST /post/<post_id>/like`  
**인증**: 필요

**응답 200 (토글)**:
```json
{
  "message": "좋아요를 추가했습니다",  // 또는 "좋아요를 취소했습니다"
  "liked": true,  // 또는 false
  "like_count": 11
}
```

---

### 3.7 게시글 좋아요 취소

**Endpoint**: `DELETE /post/<post_id>/like`  
**인증**: 필요

**응답 200 (성공)**:
```json
{
  "message": "좋아요가 취소되었습니다",
  "like_count": 10
}
```

**응답 404**:
```json
{
  "message": "좋아요를 찾을 수 없습니다"
}
```

---

## 4. 댓글 (Reply)

Base Path: `/reply`

### 4.1 댓글 목록 조회

**Endpoint**: `GET /reply`  
**인증**: 불필요  
**Query Parameters**:
- `post_id`: integer (필수) - 게시글 ID
- `page`: integer (기본값: 1)
- `per_page`: integer (기본값: 20)
- `order_by`: string (기본값: "asc") - `"asc"` 또는 `"desc"`

**응답 200**:
```json
{
  "top_liked_replies": [
    {
      "reply_id": 1,
      "post_id": 1,
      "user_id": 2,
      "author": {
        "nickname": "댓글러",
        "profile_img": "uuid-here"
      },
      "content": "좋아요 많은 댓글",
      "parent_id": null,
      "like_count": 50,
      "child_count": 3,
      "created_at": "2025-11-19T10:00:00",
      "updated_at": "2025-11-19T10:00:00"
    }
  ],
  "items": [
    {
      "reply_id": 2,
      "post_id": 1,
      "user_id": 3,
      "author": {
        "nickname": "댓글러2",
        "profile_img": "uuid-here"
      },
      "content": "댓글 내용",
      "parent_id": null,
      "like_count": 5,
      "child_count": 1,
      "created_at": "2025-11-19T11:00:00",
      "updated_at": "2025-11-19T11:00:00"
    }
  ],
  "total": 100,
  "pages": 5,
  "page": 1,
  "per_page": 20,
  "has_next": true,
  "has_prev": false
}
```

**응답 400**:
```json
{
  "message": "post_id는 필수입니다"
}
```

---

### 4.2 댓글 작성

**Endpoint**: `POST /reply`  
**인증**: 필요  
**Content-Type**: `application/json`

**요청**:
```json
{
  "post_id": 1,  // 필수
  "content": "댓글 내용",  // 필수
  "parent_id": 5  // 선택 (대댓글인 경우)
}
```

**응답 201 (성공)**:
```json
{
  "message": "댓글이 작성되었습니다",
  "reply": {
    "reply_id": 10,
    "post_id": 1,
    "user_id": 2,
    "content": "댓글 내용",
    "parent_id": null,
    "created_at": "2025-11-19T13:00:00",
    "updated_at": "2025-11-19T13:00:00"
  }
}
```

**응답 400**:
```json
{
  "message": "post_id와 content는 필수입니다"
}
```

**응답 404**:
```json
{
  "message": "게시글을 찾을 수 없습니다"
}
// 또는
{
  "message": "부모 댓글을 찾을 수 없습니다"
}
```

---

### 4.3 댓글 상세 조회

**Endpoint**: `GET /reply/<reply_id>`  
**인증**: 불필요

**응답 200**:
```json
{
  "reply_id": 1,
  "post_id": 1,
  "author": {
    "user_id": 2,
    "username": "commenter",
    "nickname": "댓글러",
    "profile_img": "uuid-here"
  },
  "content": "댓글 내용",
  "parent_id": null,
  "like_count": 10,
  "created_at": "2025-11-19T10:00:00",
  "updated_at": "2025-11-19T10:00:00"
}
```

---

### 4.4 댓글 수정

**Endpoint**: `PUT /reply/<reply_id>`  
**인증**: 필요 (작성자만)  
**Content-Type**: `application/json`

**요청**:
```json
{
  "content": "수정된 댓글 내용"  // 필수
}
```

**응답 200 (성공)**:
```json
{
  "message": "댓글이 수정되었습니다",
  "reply": {
    // Reply 객체 (4.3 참고)
  }
}
```

**응답 403**:
```json
{
  "message": "댓글을 수정할 권한이 없습니다"
}
```

---

### 4.5 댓글 삭제

**Endpoint**: `DELETE /reply/<reply_id>`  
**인증**: 필요 (작성자 또는 관리자)

**응답 200 (성공)**:
```json
{
  "message": "댓글이 삭제되었습니다"
}
```

**응답 403**:
```json
{
  "message": "댓글을 삭제할 권한이 없습니다"
}
```

---

### 4.6 댓글 좋아요

**Endpoint**: `POST /reply/<reply_id>/like`  
**인증**: 필요

**응답 200 (토글)**:
```json
{
  "message": "좋아요를 추가했습니다",  // 또는 "좋아요를 취소했습니다"
  "liked": true,  // 또는 false
  "like_count": 11
}
```

---

### 4.7 댓글 좋아요 취소

**Endpoint**: `DELETE /reply/<reply_id>/like`  
**인증**: 필요

**응답 200**: 4.6과 유사

---

### 4.8 대댓글 목록 조회

**Endpoint**: `GET /reply/<reply_id>/replies`  
**인증**: 불필요  
**Query Parameters**:
- `page`: integer (기본값: 1)
- `per_page`: integer (기본값: 20)
- `order_by`: string (기본값: "asc")

**응답 200**:
```json
{
  "items": [
    {
      "reply_id": 5,
      "post_id": 1,
      "user_id": 3,
      "author": {
        "nickname": "대댓글러",
        "profile_img": "uuid-here"
      },
      "content": "대댓글 내용",
      "parent_id": 1,
      "like_count": 2,
      "child_count": 0,
      "created_at": "2025-11-19T12:00:00",
      "updated_at": "2025-11-19T12:00:00"
    }
  ],
  "total": 10,
  "pages": 1,
  "page": 1,
  "per_page": 20,
  "has_next": false,
  "has_prev": false
}
```

---

## 5. 알림 (Notification)

Base Path: `/notification`

### 5.1 알림 생성

**Endpoint**: `POST /notification`  
**인증**: 필요  
**Content-Type**: `application/json`

**요청**:
```json
{
  "user_id": 2,  // 필수 - 알림 받을 사용자
  "type": "POST_LIKE",  // 필수 - 알림 타입
  "post_id": 1,  // 선택
  "reply_id": 5,  // 선택
  "mention_id": 3,  // 선택
  "product_id": 10  // 선택
}
```

**알림 타입**:
- `POST_LIKE`: 게시글 좋아요
- `REPLY`: 댓글 작성
- `REPLY_TO_REPLY`: 대댓글 작성
- `REPLY_LIKE`: 댓글 좋아요
- `MENTION`: 멘션
- `FRIEND_REQUEST`: 친구 요청
- `FOLLOW`: 팔로우
- `COMMENT`: 댓글 (일반)
- `PRODUCT_RECOMMENDATION`: 제품 추천

**응답 201 (성공)**:
```json
{
  "message": "알림이 생성되었습니다",
  "notification": {
    "notification_id": 1,
    "user_id": 2,
    "from_user_id": 1,
    "type": "POST_LIKE",
    "post_id": 1,
    "reply_id": null,
    "mention_id": null,
    "product_id": null,
    "is_read": false,
    "created_at": "2025-11-19T13:00:00"
  }
}
```

**응답 400**:
```json
{
  "message": "user_id와 type은 필수입니다"
}
// 또는
{
  "message": "유효하지 않은 알림 타입입니다"
}
```

---

### 5.2 내 알림 목록

**Endpoint**: `GET /notification/me`  
**인증**: 필요  
**Query Parameters**:
- `page`: integer (기본값: 1)
- `per_page`: integer (기본값: 20)
- `is_read`: boolean (선택) - `true` 또는 `false`

**응답 200**:
```json
{
  "items": [
    {
      "notification_id": 1,
      "user_id": 2,
      "from_user_id": 1,
      "from_user": {
        "user_id": 1,
        "username": "sender",
        "nickname": "보낸사람",
        "profile_img": "uuid-here"
      },
      "type": "POST_LIKE",
      "post_id": 1,
      "reply_id": null,
      "mention_id": null,
      "product_id": null,
      "is_read": false,
      "created_at": "2025-11-19T13:00:00"
    }
  ],
  "total": 50,
  "pages": 3,
  "page": 1,
  "per_page": 20,
  "has_next": true,
  "has_prev": false
}
```

---

### 5.3 읽지 않은 알림 개수

**Endpoint**: `GET /notification/unread-count`  
**인증**: 필요

**응답 200**:
```json
{
  "unread_count": 5
}
```

---

### 5.4 알림 읽음 처리

**Endpoint**: `PATCH /notification/<notification_id>`  
**인증**: 필요  
**Content-Type**: `application/json`

**요청**:
```json
{
  "is_read": true
}
```

**응답 200 (성공)**:
```json
{
  "message": "알림이 업데이트되었습니다",
  "notification": {
    // Notification 객체 (5.2 참고)
  }
}
```

**응답 403**:
```json
{
  "message": "알림을 수정할 권한이 없습니다"
}
```

---

### 5.5 모든 알림 읽음 처리

**Endpoint**: `PATCH /notification/mark-all-read`  
**인증**: 필요

**응답 200 (성공)**:
```json
{
  "message": "모든 알림을 읽음 처리했습니다",
  "updated_count": 5
}
```

---

### 5.6 알림 삭제

**Endpoint**: `DELETE /notification/<notification_id>`  
**인증**: 필요

**응답 200 (성공)**:
```json
{
  "message": "알림이 삭제되었습니다"
}
```

**응답 403**:
```json
{
  "message": "알림을 삭제할 권한이 없습니다"
}
```

---

### 5.7 모든 알림 조회 (관리자용)

**Endpoint**: `GET /notification/all`  
**인증**: 필요 (관리자)  
**Query Parameters**: 5.2와 동일

**응답 200**: 5.2와 동일한 구조

---

## 6. 멘션 (Mention)

Base Path: `/mention`

### 6.1 멘션 생성

**Endpoint**: `POST /mention`  
**인증**: 필요  
**Content-Type**: `application/json`

**요청**:
```json
{
  "mentioned_user_id": 2,  // 필수
  "post_id": 1  // post_id 또는 reply_id 중 하나 필수
  // 또는
  "reply_id": 5
}
```

**응답 201 (성공)**:
```json
{
  "message": "멘션 생성 완료",
  "mention": {
    "mention_id": 1,
    "mentioner_id": 1,
    "mentioner_username": "mentioner",
    "mentioner_nickname": "멘션한사람",
    "mentioned_user_id": 2,
    "mentioned_username": "mentioned",
    "post_id": 1,
    "reply_id": null,
    "mention_type": "POST",  // "POST" 또는 "REPLY"
    "created_at": "2025-11-19T13:00:00",
    "is_checked": false
  }
}
```

**응답 400**:
```json
{
  "message": "mentioned_user_id is required"
}
// 또는
{
  "message": "정확히 하나의 대상(post_id or reply_id)만 지정해야 합니다"
}
// 또는
{
  "message": "자기 자신을 멘션할 수 없습니다"
}
// 또는
{
  "message": "이미 존재하는 멘션입니다"
}
```

**응답 404**:
```json
{
  "message": "해당 사용자를 찾을 수 없습니다"
}
// 또는
{
  "message": "해당 게시글을 찾을 수 없습니다"
}
// 또는
{
  "message": "해당 댓글을 찾을 수 없습니다"
}
```

**참고**: 멘션 생성 시 자동으로 `MENTION` 타입의 알림이 생성됩니다.

---

### 6.2 받은 멘션 조회

**Endpoint**: `GET /mention/mine`  
**인증**: 필요

**응답 200**:
```json
{
  "mentions": [
    {
      // Mention 객체 (6.1 참고)
    }
  ]
}
```

---

### 6.3 보낸 멘션 조회

**Endpoint**: `GET /mention/sent`  
**인증**: 필요

**응답 200**: 6.2와 동일한 구조

---

### 6.4 게시글별 멘션 조회

**Endpoint**: `GET /mention/post/<post_id>`  
**인증**: 필요

**응답 200**: 6.2와 동일한 구조

**응답 404**:
```json
{
  "message": "해당 게시글을 찾을 수 없습니다"
}
```

---

### 6.5 모든 멘션 조회 (관리자용)

**Endpoint**: `GET /mention/all`  
**인증**: 필요

**응답 200**: 6.2와 동일한 구조

---

### 6.6 타입별 멘션 조회

**Endpoint**: `GET /mention/type/<mention_type>`  
**인증**: 필요  
**Parameters**:
- `mention_type`: "POST" 또는 "REPLY"

**응답 200**: 6.2와 동일한 구조

**응답 400**:
```json
{
  "message": "유효하지 않은 타입입니다 (POST or REPLY)"
}
```

---

## 7. 즐겨찾기 (Favorite)

Base Path: `/favorite`

### 7.1 즐겨찾기 추가

**Endpoint**: `POST /favorite`  
**인증**: 필요  
**Content-Type**: `application/json`

**요청**:
```json
{
  "type": "POST",  // 필수 - "POST", "PRODUCT", "ROUTE"
  "target_id": 1  // 필수 - 대상 ID
}
```

**응답 201 (성공)**:
```json
{
  "message": "즐겨찾기에 추가되었습니다",
  "favorite": {
    "favorite_id": 1,
    "user_id": 1,
    "type": "POST",
    "target_id": 1,
    "created_at": "2025-11-19T13:00:00"
  }
}
```

**응답 400**:
```json
{
  "message": "type과 target_id는 필수입니다"
}
// 또는
{
  "message": "이미 즐겨찾기에 추가되어 있습니다"
}
```

---

### 7.2 즐겨찾기 목록

**Endpoint**: `GET /favorite`  
**인증**: 필요  
**Query Parameters**:
- `type`: string (선택) - "POST", "PRODUCT", "ROUTE"
- `page`: integer (기본값: 1)
- `per_page`: integer (기본값: 20)

**응답 200**:
```json
{
  "items": [
    {
      "favorite_id": 1,
      "user_id": 1,
      "type": "POST",
      "target_id": 1,
      "created_at": "2025-11-19T13:00:00",
      "target": {
        // Post, Product, 또는 Route 객체
      }
    }
  ],
  "total": 50,
  "pages": 3,
  "page": 1,
  "per_page": 20,
  "has_next": true,
  "has_prev": false
}
```

---

### 7.3 즐겨찾기 삭제

**Endpoint**: `DELETE /favorite/<favorite_id>`  
**인증**: 필요

**응답 200 (성공)**:
```json
{
  "message": "즐겨찾기가 삭제되었습니다"
}
```

**응답 403**:
```json
{
  "message": "즐겨찾기를 삭제할 권한이 없습니다"
}
```

---

## 8. 피드 (Feed)

Base Path: `/feed`

### 8.1 피드 조회

**Endpoint**: `GET /feed`  
**인증**: 필요  
**Query Parameters**:
- `page`: integer (기본값: 1)
- `per_page`: integer (기본값: 20)

**응답 200**:
```json
{
  "items": [
    {
      "feed_item_id": 1,
      "user_id": 1,
      "type": "POST",  // "POST", "FOLLOW", "FRIEND"
      "target_id": 1,
      "created_at": "2025-11-19T13:00:00",
      "target": {
        // Post, User 객체 등
      }
    }
  ],
  "total": 200,
  "pages": 10,
  "page": 1,
  "per_page": 20,
  "has_next": true,
  "has_prev": false
}
```

---

## 9. 제품 (Product)

Base Path: `/product`

### 9.1 제품 목록

**Endpoint**: `GET /product`  
**인증**: 불필요  
**Query Parameters**:
- `page`: integer (기본값: 1)
- `per_page`: integer (기본값: 20)
- `category`: string (선택)

**응답 200**:
```json
{
  "items": [
    {
      "product_id": 1,
      "name": "제품명",
      "description": "제품 설명",
      "price": 50000,
      "category": "ACCESSORY",
      "image_url": "https://example.com/image.jpg",
      "rating": 4.5,
      "review_count": 100,
      "created_at": "2025-11-19T10:00:00"
    }
  ],
  "total": 100,
  "pages": 5,
  "page": 1,
  "per_page": 20,
  "has_next": true,
  "has_prev": false
}
```

---

### 9.2 제품 상세

**Endpoint**: `GET /product/<product_id>`  
**인증**: 불필요

**응답 200**:
```json
{
  "product_id": 1,
  "name": "제품명",
  "description": "제품 설명",
  "price": 50000,
  "category": "ACCESSORY",
  "image_url": "https://example.com/image.jpg",
  "rating": 4.5,
  "review_count": 100,
  "reviews": [
    {
      "review_id": 1,
      "user_id": 2,
      "author": {
        "nickname": "리뷰어",
        "profile_img": "uuid-here"
      },
      "rating": 5,
      "content": "좋은 제품입니다",
      "created_at": "2025-11-19T12:00:00"
    }
  ],
  "created_at": "2025-11-19T10:00:00"
}
```

---

## 10. 신고 (Report)

Base Path: `/report`

### 10.1 신고 생성

**Endpoint**: `POST /report`  
**인증**: 필요  
**Content-Type**: `application/json`

**요청**:
```json
{
  "type": "POST",  // 필수 - "POST", "REPLY", "USER"
  "target_id": 1,  // 필수 - 신고 대상 ID
  "reason": "spam",  // 필수 - "spam", "abuse", "inappropriate", "other"
  "description": "상세 설명"  // 선택
}
```

**응답 201 (성공)**:
```json
{
  "message": "신고가 접수되었습니다",
  "report": {
    "report_id": 1,
    "user_id": 1,
    "type": "POST",
    "target_id": 1,
    "reason": "spam",
    "description": "상세 설명",
    "status": "pending",  // "pending", "reviewed", "resolved"
    "created_at": "2025-11-19T13:00:00"
  }
}
```

**응답 400**:
```json
{
  "message": "type, target_id, reason은 필수입니다"
}
```

---

### 10.2 신고 목록 (관리자용)

**Endpoint**: `GET /report`  
**인증**: 필요 (관리자)  
**Query Parameters**:
- `page`: integer (기본값: 1)
- `per_page`: integer (기본값: 20)
- `status`: string (선택) - "pending", "reviewed", "resolved"

**응답 200**:
```json
{
  "items": [
    {
      // Report 객체 (10.1 참고)
    }
  ],
  "total": 50,
  "pages": 3,
  "page": 1,
  "per_page": 20,
  "has_next": true,
  "has_prev": false
}
```

---

## 11. 관리자 (Admin)

Base Path: `/admin`

### 11.1 사용자 관리

**Endpoint**: `GET /admin/users`  
**인증**: 필요 (관리자)  
**Query Parameters**:
- `page`: integer (기본값: 1)
- `per_page`: integer (기본값: 20)

**응답 200**:
```json
{
  "items": [
    {
      // User 객체 (1.6 참고)
    }
  ],
  "total": 1000,
  "pages": 50,
  "page": 1,
  "per_page": 20,
  "has_next": true,
  "has_prev": false
}
```

---

### 11.2 사용자 계정 정지/해제

**Endpoint**: `PATCH /admin/users/<user_id>/suspend`  
**인증**: 필요 (관리자)  
**Content-Type**: `application/json`

**요청**:
```json
{
  "is_expired": true  // true: 정지, false: 해제
}
```

**응답 200 (성공)**:
```json
{
  "message": "사용자 계정이 정지되었습니다",  // 또는 "해제되었습니다"
  "user": {
    // User 객체
  }
}
```

---

## 12. 경로 (Route)

Base Path: `/route`

### 12.1 경로 검색

**Endpoint**: `GET /route/search`  
**인증**: 불필요  
**Query Parameters**:
- `start_lat`: float (필수) - 출발지 위도
- `start_lng`: float (필수) - 출발지 경도
- `end_lat`: float (필수) - 도착지 위도
- `end_lng`: float (필수) - 도착지 경도

**응답 200**:
```json
{
  "route": {
    "distance": 5000,  // 미터
    "duration": 1200,  // 초
    "coordinates": [
      {"lat": 37.5665, "lng": 126.9780},
      {"lat": 37.5666, "lng": 126.9781}
    ]
  }
}
```

---

## 공통 응답

### 에러 응답

모든 에러 응답은 다음 형식을 따릅니다:

```json
{
  "message": "에러 메시지"
}
```

### HTTP 상태 코드

- `200 OK`: 성공
- `201 Created`: 리소스 생성 성공
- `400 Bad Request`: 잘못된 요청
- `401 Unauthorized`: 인증 필요
- `403 Forbidden`: 권한 없음
- `404 Not Found`: 리소스 없음
- `409 Conflict`: 중복/충돌
- `415 Unsupported Media Type`: 잘못된 Content-Type
- `500 Internal Server Error`: 서버 오류

### 페이지네이션

페이지네이션이 적용된 모든 엔드포인트는 다음 구조를 따릅니다:

```json
{
  "items": [],
  "total": 100,
  "pages": 5,
  "page": 1,
  "per_page": 20,
  "has_next": true,
  "has_prev": false
}
```

### 인증 헤더

보호된 엔드포인트 요청 시:

```
Authorization: Bearer <access_token>
```

---

## 최근 변경사항

### 2025-11-19

1. **통합 로그인 엔드포인트 추가**
   - `POST /auth/login`이 일반 로그인 + OAuth 로그인 통합
   - 기존 `/auth/login/google`, `/auth/login/kakao`, `/auth/login/naver`는 deprecated

2. **HTTP 인터셉터 추가**
   - 모든 4xx, 5xx 에러 자동 로깅
   - 로그 파일: `logs/error.log` (UTF-8)
   - 민감 정보 자동 마스킹 (password, token 등)

3. **대댓글 페이지네이션 개선**
   - `GET /reply/<reply_id>/replies`에 페이지네이션 정보 추가
   - 응답 형식이 `GET /reply`와 일치하도록 변경

4. **멘션 모듈 마이그레이션 완료**
   - 레거시 코드에서 `apps/mention/` 구조로 이동
   - CASCADE 제약조건 적용
   - 6개 엔드포인트 모두 정상 작동

5. **알림 시스템 통합**
   - 9가지 알림 타입 지원
   - 읽음/읽지않음 필터링
   - 일괄 읽음 처리 기능

---

## 13. 즐겨찾기 장소 (Place)

Base Path: `/place`  
인증: JWT Bearer 헤더 필수 (`Authorization: Bearer <access_token>`)  
CSRF: JWT 프레임워크의 기본 설정 준수, 헤더 기반 요청 시 추가 CSRF 토큰 불필요.

### 13.1 장소 생성
**Endpoint**: `POST /place`  
**Body (application/json)**:
```json
{
  "name": "Home",
  "lat": 37.5,
  "lon": 127.0,
  "point": 4.5,
  "radius": 50,
  "description": "위치 설명",
  "is_public": false
}
```
**성공 201**:
```json
{
  "message": "Place created",
  "place": {
    "place_id": 1,
    "name": "Home",
    "lat": 37.5,
    "lon": 127.0,
    "point": 4.5,
    "radius": 50.0,
    "description": "위치 설명",
    "is_public": false,
    "created_at": "2025-11-19T10:00:00",
    "updated_at": "2025-11-19T10:00:00",
    "user_id": 3
  }
}
```
**검증 실패 400**: `{"message": "Invalid input", "errors": ["lat must be >= -90", ...]}`

### 13.2 목록/단건 조회
- `GET /place?page=1&per_page=20` → 현재 사용자 즐겨찾기 목록, 페이지네이션 필드(`items`, `total`, `pages`, `page`, `per_page`).
- `GET /place/<place_id>` → 소유자만 접근 가능, 없으면 404, 권한 없으면 403.

### 13.3 수정/삭제
- `PUT /place/<place_id>`: 부분 업데이트 허용(`name`, `lat`, `lon`, `point`, `radius`, `description`, `is_public`), 입력 검증 동일, 소유자만 200, 권한 없으면 403.
- `DELETE /place/<place_id>`: 소유자만 삭제 가능, 성공 시 `{"message": "Place deleted"}`.

입력 규칙: `name` 필수, `lat` ∈ [-90, 90], `lon` ∈ [-180, 180], `point` ∈ [0, 5], `radius` 숫자.  
에러 시 명확한 메시지와 HTTP 400/403/404/401 상태 코드 반환.

---

## 개발 가이드

### 새 엔드포인트 추가 시

1. 해당 모듈의 `views.py`에 엔드포인트 추가
2. 이 문서에 상세 스펙 업데이트
3. 요청/응답 객체의 모든 필드 명시
4. 에러 케이스별 응답 예시 추가

### API 테스트

```bash
# 서버 시작
python apps/app.py

# Postman 또는 curl로 테스트
curl -X POST http://192.168.1.86:8002/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test123"}'

# 에러 로그 확인
tail -f logs/error.log
```

---

**문서 끝**
