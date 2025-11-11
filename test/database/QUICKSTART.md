# 빠른 참조 - 테스트 데이터 생성

## 🚀 가장 자주 사용하는 명령어

### 모든 것을 한 번에 생성
```bash
pytest test/database/generate_all.py test/database/verify_all.py -v -s
```

### 생성만 하기 (확인 없이)
```bash
pytest test/database/generate_all.py -v -s
```

### 데이터베이스에 있는 것만 확인
```bash
pytest test/database/verify_all.py -v -s
```

## 📊 생성되는 데이터

- **12명 사용자**: 10명 일반 사용자 + 2명 관리자 (모두 비밀번호: `1234`)
- **20개 게시글**: 4개 카테고리에 분산
- **약 100개 댓글**: 일반 댓글과 중첩 댓글 혼합
- **4개 카테고리**: STORY, ROUTE, REVIEW, REPORT

## 🗄️ 데이터베이스 정보

- **테스트 DB**: `404found_test` (운영과 분리됨)
- **운영 DB**: `404found` (테스트에 의해 영향받지 않음)
- **연결**: `mysql+pymysql://root:1234@localhost:3306/404found_test`

## 🔧 최초 설정

```bash
# 1. 테스트 데이터베이스 생성 (한 번만)
python test/setup_test_db.py

# 2. 데이터 생성
pytest test/database/generate_all.py -v -s

# 3. 확인
pytest test/database/verify_all.py -v -s
```

## 🔄 데이터베이스 초기화

모든 테스트 데이터를 지우고 새로 시작하려면:

```bash
# 테스트 데이터베이스 삭제 및 재생성
python test/setup_test_db.py

# 모든 데이터 재생성
pytest test/database/generate_all.py -v -s
```

## 🎯 개별 생성기 (고급)

```bash
# 순서대로 생성
pytest test/database/gen_user.py -v -s          # 사용자 먼저
pytest test/database/gen_post.py -v -s          # 그 다음 게시글
pytest test/database/gen_reply.py -v -s         # 그 다음 댓글

# 또는 한 번에
pytest test/database/gen_user.py test/database/gen_post.py test/database/gen_reply.py -v -s
```

## 🔍 샘플 로그인 정보

모든 사용자의 비밀번호는 동일합니다: `1234`

**일반 사용자:**
- user1@mail.com
- user2@mail.com
- ...
- user10@mail.com

**관리자:**
- admin1@mail.com
- admin2@mail.com
