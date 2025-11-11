# 테스트 데이터 생성기

이 디렉토리는 테스트 데이터베이스를 채우기 위한 pytest 기반 데이터 생성기를 포함합니다.

## 설정

1. **테스트 데이터베이스 생성** (최초 1회만 필요):
   ```bash
   python test/setup_test_db.py
   ```

2. **데이터베이스 설정**:
   - 테스트 데이터베이스: `404found_test`
   - 운영 데이터베이스: `404found`
   - 테스트는 자동으로 별도의 테스트 데이터베이스를 사용합니다

## 사용법

### 빠른 시작 - 모든 데이터 생성
```bash
pytest test/database/generate_all.py -v -s
```
사용자, 게시글, 댓글, 카테고리를 한 번에 생성합니다.

### 개별 데이터 타입 생성

**사용자 생성:**
```bash
pytest test/database/gen_user.py -v -s
```
일반 사용자 10명과 관리자 2명을 생성합니다.

**게시글 생성:**
```bash
pytest test/database/gen_post.py -v -s
```
4개 카테고리(STORY, ROUTE, REVIEW, REPORT)로 20개 게시글을 생성합니다. 사용자가 먼저 존재해야 합니다.

**댓글 생성:**
```bash
pytest test/database/gen_reply.py -v -s
```
게시글에 대한 댓글(중첩 댓글 포함)을 생성합니다. 사용자와 게시글이 먼저 존재해야 합니다.

**순서대로 생성:**
```bash
pytest test/database/gen_user.py test/database/gen_post.py test/database/gen_reply.py -v -s
```

### 생성된 데이터 확인

**종합 확인 (권장):**
```bash
pytest test/database/verify_all.py -v -s
```
데이터베이스의 모든 데이터에 대한 완전한 보고서를 표시합니다.

**개별 확인:**

**사용자 확인:**
```bash
pytest test/database/verify_users.py -v -s
```

**게시글 확인:**
```bash
pytest test/database/verify_posts.py -v -s
```

**댓글 확인:**
```bash
pytest test/database/verify_replies.py -v -s
```

**전체 워크플로우 (생성 + 확인):**
```bash
pytest test/database/generate_all.py test/database/verify_all.py -v -s
```

## 동작 원리

- **`conftest.py`**: 테스트 픽스처와 데이터베이스 설정
  - `fixture_app`: 테스트 데이터베이스로 Flask 앱 생성
  - `clean_db`: 자동 정리 픽스처 (`@pytest.mark.no_cleanup` 마크가 있는 생성기는 건너뜀)

- **데이터 생성기**: 데이터를 유지하기 위해 `@pytest.mark.no_cleanup`으로 표시된 테스트 파일
  - `generate_all.py`: 모든 데이터를 한 번에 생성 (권장)
  - `gen_user.py`: 사용자 계정 생성 (10명 사용자 + 2명 관리자)
  - `gen_post.py`: 게시글 생성 (4개 카테고리로 20개 게시글)
  - `gen_reply.py`: 댓글 생성 (중첩 댓글 포함)
  - `gen_images.py`: 이미지 생성 (TODO)

- **확인**: 생성된 데이터를 확인하는 테스트 파일
  - `verify_all.py`: 모든 데이터에 대한 종합 보고서 (권장)
  - `verify_users.py`: 생성된 사용자 보기
  - `verify_posts.py`: 생성된 게시글 및 카테고리 보기
  - `verify_replies.py`: 생성된 댓글 보기 (일반 및 중첩)

## 새 생성기 만들기

1. `test/database/`에 새 테스트 파일 생성
2. 필요한 모델과 픽스처 임포트
3. 데이터를 유지하기 위해 `@pytest.mark.no_cleanup`으로 테스트 마크
4. 데이터베이스 작업을 위해 `fixture_app.app_context()` 사용

예시:
```python
import pytest
from app.extensions import db
from app.models.post import Post

@pytest.mark.no_cleanup
def test_generate_posts(fixture_app):
    with fixture_app.app_context():
        posts = [Post(title=f"Post {i}") for i in range(10)]
        db.session.add_all(posts)
        db.session.commit()
        print(f"✓ {len(posts)}개 게시글 생성됨")
```

## 참고 사항

- 테스트 데이터베이스는 운영 데이터베이스와 분리되어 있습니다 (`404found_test` vs `404found`)
- 데이터는 수동으로 정리하지 않는 한 실행 간에 유지됩니다
- 테스트 데이터베이스 초기화: `setup_test_db.py`로 삭제 후 재생성
- 일반 테스트(`@pytest.mark.no_cleanup` 없음)는 각 실행 후 자동으로 정리됩니다
