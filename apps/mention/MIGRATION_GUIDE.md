# Mention Module Migration Guide

## Overview
멘션(Mention) 모듈을 레거시 `app/` 구조에서 신규 `apps/mention/` 구조로 마이그레이션했습니다.

**마이그레이션 날짜:** 2024  
**소스 파일:**
- `app/models/mention.py` → `apps/mention/models.py`
- `app/blueprints/mention.py` → `apps/mention/views.py`
- `app/utils/mention_utils.py` → `apps/mention/views.py` (serialize_mention 함수 통합)

---

## Model Changes

### Mention Model
**변경 사항:** 구조 유지, 모든 CASCADE 제약조건 적용됨

| Field | Type | Legacy | Current | Notes |
|-------|------|--------|---------|-------|
| mention_id | Integer PK | ✅ | ✅ | 동일 |
| mentioner_id | FK(users) | ✅ | ✅ | CASCADE 적용 |
| mentioned_user_id | FK(users) | ✅ | ✅ | CASCADE 적용 |
| post_id | FK(posts) | ✅ | ✅ | CASCADE 적용, nullable |
| reply_id | FK(replies) | ✅ | ✅ | CASCADE 적용, nullable |
| created_at | DateTime | ✅ | ✅ | 동일 |
| is_checked | Boolean | ✅ | ✅ | 동일 |

**Constraints:**
- `check_one_target`: `(post_id IS NOT NULL AND reply_id IS NULL) OR (post_id IS NULL AND reply_id IS NOT NULL)` ✅
- `unique_mention_target`: UniqueConstraint(mentioned_user_id, post_id, reply_id) ✅

**Relationships:**
- `mentioner` → User (foreign_keys=[mentioner_id]) with backref `mentions_sent` ✅
- `mentioned_user` → User (foreign_keys=[mentioned_user_id]) with backref `mentions_received` ✅
- `post` → Post with backref `post_mentions` ✅
- `reply` → Reply with backref `reply_mentions` ✅

---

## API Endpoints Comparison

### 1. Create Mention (멘션 생성)
| Aspect | Legacy | Current | Status |
|--------|--------|---------|--------|
| Method | POST | POST | ✅ Same |
| Path | `/mention/` | `/mention/` | ✅ Same |
| Auth | JWT Required | JWT Required | ✅ Same |
| Request Body | `{mentioned_user_id, post_id/reply_id}` | `{mentioned_user_id, post_id/reply_id}` | ✅ Same |
| Response | 201 with mention object | 201 with mention object | ✅ Same |
| Auto-Notification | ✅ Creates MENTION notification | ✅ Creates MENTION notification | ✅ Same |
| Validations | Self-mention check, one target, duplicate check | Self-mention check, one target, duplicate check | ✅ Same |

### 2. Get My Mentions (받은 멘션)
| Aspect | Legacy | Current | Status |
|--------|--------|---------|--------|
| Method | GET | GET | ✅ Same |
| Path | `/mention/mine` | `/mention/mine` | ✅ Same |
| Auth | JWT Required | JWT Required | ✅ Same |
| Filter | `mentioned_user_id == current_user` | `mentioned_user_id == current_user` | ✅ Same |
| Order | DESC by created_at | DESC by created_at | ✅ Same |

### 3. Get Sent Mentions (보낸 멘션)
| Aspect | Legacy | Current | Status |
|--------|--------|---------|--------|
| Method | GET | GET | ✅ Same |
| Path | `/mention/sent` | `/mention/sent` | ✅ Same |
| Auth | JWT Required | JWT Required | ✅ Same |
| Filter | `mentioner_id == current_user` | `mentioner_id == current_user` | ✅ Same |

### 4. Get Post Mentions (게시글별 멘션)
| Aspect | Legacy | Current | Status |
|--------|--------|---------|--------|
| Method | GET | GET | ✅ Same |
| Path | `/mention/post/<post_id>` | `/mention/post/<post_id>` | ✅ Same |
| Auth | JWT Required | JWT Required | ✅ Same |
| Filter | `post_id == parameter` | `post_id == parameter` | ✅ Same |

### 5. Get All Mentions (전체 멘션 - 관리자용)
| Aspect | Legacy | Current | Status |
|--------|--------|---------|--------|
| Method | GET | GET | ✅ Same |
| Path | `/mention/all` | `/mention/all` | ✅ Same |
| Auth | JWT Required | JWT Required | ⚠️ Admin check needed |
| Note | No admin check | TODO: Add admin check | 🔄 Enhancement needed |

### 6. Get Mentions By Type (타입별 멘션)
| Aspect | Legacy | Current | Status |
|--------|--------|---------|--------|
| Method | GET | GET | ✅ Same |
| Path | `/mention/type/<type>` | `/mention/type/<type>` | ✅ Same |
| Auth | JWT Required | JWT Required | ✅ Same |
| Types | "POST", "REPLY" | "POST", "REPLY" | ✅ Same |
| Filter | `mentioned_user_id == current_user + type` | `mentioned_user_id == current_user + type` | ✅ Same |

---

## serialize_mention() Function

**Legacy Location:** `app/utils/mention_utils.py`  
**Current Location:** `apps/mention/views.py` (integrated as helper function)

### Return Structure (동일)
```python
{
    "mention_id": int,
    "mentioner_id": int,
    "mentioner_username": str,
    "mentioner_nickname": str,
    "mentioned_user_id": int,
    "mentioned_username": str,
    "post_id": int or None,
    "reply_id": int or None,
    "mention_type": "POST" or "REPLY",  # Derived field
    "created_at": ISO datetime string,
    "is_checked": bool
}
```

---

## Breaking Changes

**✅ None** - 완전한 하위 호환성 유지

모든 엔드포인트가 동일한 경로, 요청/응답 형식을 유지합니다.

---

## New Features / Enhancements

### ✅ CASCADE Constraints
모든 ForeignKey에 `ondelete="CASCADE"` 적용:
- User 삭제 시 관련 멘션 자동 삭제
- Post 삭제 시 해당 게시글의 멘션 자동 삭제
- Reply 삭제 시 해당 댓글의 멘션 자동 삭제

### 🔄 Admin Permission Check (TODO)
`/mention/all` 엔드포인트에 관리자 권한 체크 추가 권장

---

## Testing Checklist

### Core Functionality
- [ ] POST `/mention/` - 멘션 생성 및 알림 자동 생성
- [ ] GET `/mention/mine` - 받은 멘션 조회
- [ ] GET `/mention/sent` - 보낸 멘션 조회
- [ ] GET `/mention/post/<id>` - 게시글별 멘션 조회
- [ ] GET `/mention/all` - 전체 멘션 조회
- [ ] GET `/mention/type/<type>` - 타입별 멘션 조회

### Validation Tests
- [ ] 자기 자신 멘션 방지 (400 error)
- [ ] 중복 멘션 방지 (400 error)
- [ ] 하나의 대상만 지정 (post OR reply, not both) (400 error)
- [ ] 존재하지 않는 사용자 멘션 (404 error)
- [ ] 존재하지 않는 post/reply 멘션 (404 error)

### Cascade Tests
- [ ] User 삭제 시 mentioner_id 기준 멘션 삭제
- [ ] User 삭제 시 mentioned_user_id 기준 멘션 삭제
- [ ] Post 삭제 시 관련 멘션 삭제
- [ ] Reply 삭제 시 관련 멘션 삭제

### Notification Integration
- [ ] 멘션 생성 시 MENTION 타입 알림 자동 생성 확인
- [ ] 알림에 올바른 post_id/reply_id 포함 확인

---

## Migration Notes

1. **Blueprint Registration:** `apps/app.py`에 mention blueprint 등록 완료
2. **Model Import:** `import_all_models()` 함수에 Mention 모델 포함됨
3. **serialize_mention():** 별도 utils 파일 대신 views.py에 헬퍼 함수로 통합
4. **Legacy Code Marked:** 레거시 파일에 마이그레이션 주석 추가됨

---

## Developer Notes

### Key Logic to Understand
1. **One Target Constraint:** 멘션은 게시글 OR 댓글 중 하나만 대상으로 가짐 (CheckConstraint)
2. **Auto-Notification:** 멘션 생성 시 자동으로 Notification 생성 (`type="MENTION"`)
3. **Duplicate Prevention:** UniqueConstraint로 동일한 사용자를 같은 대상에 중복 멘션 불가
4. **Derived mention_type:** serialize 시 post_id 존재 여부로 "POST" 또는 "REPLY" 판단

### Future Enhancements
- Admin permission check for `/mention/all`
- Pagination for large mention lists
- Mark mention as checked endpoint (like notification)
- Bulk mention operations
