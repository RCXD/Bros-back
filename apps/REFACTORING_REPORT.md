# Bros-back 리팩토링 아키텍처

## 개요

이 문서는 `./app`에서 `./apps`로 모듈화된 블루프린트 구조로 리팩토링한 아키텍처를 설명합니다.

## 디렉토리 구조

```
apps/
├── app.py                      # 애플리케이션 팩토리
├── config/
│   ├── common.py              # 공유 설정
│   └── server.py              # Flask 확장 (db, jwt 등)
├── common/
│   ├── jwt_handlers.py        # JWT 콜백 및 핸들러
│   └── __init__.py
├── auth/                      # 인증 모듈
│   ├── models.py             # User 모델
│   ├── views.py              # 인증 라우트 (회원가입, 로그인 등)
│   ├── utils.py              # 인증 유틸리티 (token_provider)
│   └── __init__.py
├── user/                      # 사용자 프로필 및 소셜
│   ├── models.py             # Follow, Friend 모델
│   ├── views.py              # 프로필, 팔로우 라우트
│   └── __init__.py
├── post/                      # 게시글 관리
│   ├── models.py             # Post, Like 모델
│   ├── views.py              # 게시글 CRUD 라우트
│   ├── utils.py              # 게시글 유틸리티
│   └── __init__.py
├── reply/                     # 댓글 및 답글
│   ├── models.py             # Reply 모델
│   ├── views.py              # 댓글 라우트
│   └── __init__.py
├── feed/                      # 사용자 피드 및 타임라인
│   ├── views.py              # 피드 라우트
│   └── __init__.py
├── route/                     # 내비게이션 및 경로
│   ├── models.py             # MyPath 모델
│   ├── views.py              # 경로 라우트
│   └── __init__.py
├── product/                   # 제품 리뷰
│   ├── models.py             # Product 모델
│   ├── views.py              # 제품 라우트
│   └── __init__.py
├── favorite/                  # 북마크 및 즐겨찾기
│   ├── models.py             # Favorite 모델
│   ├── views.py              # 즐겨찾기 라우트
│   └── __init__.py
├── detector/                  # AI 탐지 서비스
│   ├── views.py              # 탐지 라우트
│   ├── utils.py              # AI 유틸리티
│   └── __init__.py
├── security/                  # 신고 및 모더레이션
│   ├── models.py             # Report 모델
│   ├── views.py              # 보안 라우트
│   └── __init__.py
├── admin/                     # 관리자 기능
│   ├── views.py              # 관리자 라우트
│   └── __init__.py
└── test/                      # 테스트 엔드포인트
    ├── views.py              # 테스트 라우트
    └── __init__.py
```

## 레거시 구조와의 주요 변경사항

### 1. **모듈화된 블루프린트 아키텍처**

**이전 (`./app`):**
```python
app/
├── blueprints/
│   ├── auth.py          # 모든 인증 코드가 한 파일에
│   ├── post.py          # 모든 게시글 코드가 한 파일에
│   └── ...
├── models/
│   ├── user.py
│   ├── post.py
│   └── ...
└── utils/
    ├── user_utils.py
    └── ...
```

**이후 (`./apps`):**
```python
apps/
├── auth/
│   ├── models.py        # 인증 관련 모델
│   ├── views.py         # 인증 라우트
│   └── utils.py         # 인증 유틸리티
├── post/
│   ├── models.py        # 게시글 관련 모델
│   ├── views.py         # 게시글 라우트
│   └── utils.py         # 게시글 유틸리티
└── ...
```

### 2. **설정 관리**

**이전:**
- 단일 `config.py` 파일
- 환경별 설정 없음

**이후:**
```python
# apps/config/common.py
class Config:              # 기본 설정
class DevelopmentConfig:   # 개발 환경
class ProductionConfig:    # 프로덕션 환경
class TestConfig:          # 테스트 환경

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'test': TestConfig,
}
```

### 3. **애플리케이션 팩토리 패턴**

**이전:**
```python
# 직접 앱 생성
app = Flask(__name__)
```

**이후:**
```python
# apps/app.py
def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    # ...
    return app
```

### 4. **중앙화된 확장**

**이전:**
```python
# app/extensions.py
db = SQLAlchemy()
```

**이후:**
```python
# apps/config/server.py
db = SQLAlchemy()
migrate = Migrate()
cors = CORS()
jwt = JWTManager()
```

## 모듈 구조 패턴

각 모듈은 다음 패턴을 따릅니다:

```python
module_name/
├── __init__.py       # 모듈 초기화
├── models.py         # 데이터베이스 모델
├── views.py          # 라우트 핸들러 (Blueprint)
├── utils.py          # 헬퍼 함수 (선택)
└── forms.py          # 폼 검증 (선택)
```

### 예시: Auth 모듈

```python
# apps/auth/models.py
class User(db.Model):
    # User 모델 정의

# apps/auth/views.py
from flask import Blueprint
bp = Blueprint("auth", __name__)

@bp.route("/login", methods=["POST"])
def login():
    # 로그인 로직

# apps/auth/utils.py
def token_provider(user_id):
    # JWT 토큰 생성
```

## 설정

### 개발 환경
```python
from apps.app import create_app

app = create_app('development')
app.run(debug=True)
```

### 프로덕션 환경
```python
from apps.app import create_app

app = create_app('production')
# 프로덕션 WSGI 서버 사용 (gunicorn, uwsgi)
```

### 테스트 환경
```python
from apps.app import create_app

app = create_app('test')
# 테스트 실행
```

## 블루프린트 등록

블루프린트는 `apps/app.py`에서 자동으로 등록됩니다:

```python
def register_blueprints(app):
    from apps.auth.views import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix="/auth")
    
    from apps.post.views import bp as post_bp
    app.register_blueprint(post_bp, url_prefix="/post")
    # ...
```

## 데이터베이스 모델

모델은 이제 모듈별로 분산되어 있지만 동일한 `db` 인스턴스를 공유합니다:

```python
# apps/auth/models.py
from apps.config.server import db

class User(db.Model):
    __tablename__ = "users"
    # ...

# apps/post/models.py
from apps.config.server import db
from apps.auth.models import User

class Post(db.Model):
    __tablename__ = "posts"
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    # ...
```

## 레거시 코드 마이그레이션

### 1단계: 설정 복사
- ✅ `app/config.py` → `apps/config/common.py`
- ✅ `app/extensions.py` → `apps/config/server.py`

### 2단계: JWT 핸들러 복사
- ✅ `app/jwt_handlers.py` → `apps/common/jwt_handlers.py`

### 3단계: 모델 마이그레이션
- ✅ `app/models/user.py` → `apps/auth/models.py`
- ⏳ `app/models/post.py` → `apps/post/models.py` (예정)
- ⏳ `app/models/*.py` → 각 모듈로 (예정)

### 4단계: 블루프린트 마이그레이션
- ✅ `app/blueprints/auth.py` → `apps/auth/views.py` (기본 구조)
- ⏳ 기타 블루프린트 (예정)

### 5단계: 유틸리티 마이그레이션
- ✅ `app/utils/user_utils.py` → `apps/auth/utils.py`
- ⏳ 기타 유틸리티 (예정)

## 향후 계획

1. **Auth 모듈 완성** - 레거시에서 전체 인증 로직 구현
2. **Post 모듈 마이그레이션** - 모델, 뷰, 유틸리티 복사
3. **Reply 모듈 마이그레이션** - 댓글 및 중첩 답글
4. **User 모듈 마이그레이션** - Follow/Friend 관계
5. **Route 모듈 마이그레이션** - 내비게이션 및 경로
6. **Detector 모듈 마이그레이션** - AI 탐지 서비스
7. **이미지 유틸리티 추가** - 이미지 업로드, 압축, 저장
8. **테스트 추가** - 단위 테스트 및 통합 테스트
9. **문서 업데이트** - API 문서화

## 새 구조의 장점

1. **모듈성** - 각 모듈이 독립적으로 구성됨
2. **확장성** - 새 모듈 추가가 용이함
3. **유지보수성** - 명확한 관심사 분리
4. **테스트 가능성** - 모듈을 독립적으로 테스트 가능
5. **설정 관리** - 환경별 설정 관리
6. **재사용성** - 공통 모듈에서 유틸리티 공유

## 애플리케이션 실행

```bash
# 개발 환경
python apps/app.py

# 프로덕션 환경 (gunicorn 사용)
gunicorn "apps.app:create_app('production')" --bind 0.0.0.0:8000

# 테스트
pytest
```

## 레거시 호환성

리팩토링된 코드는 다음과 호환성을 유지합니다:
- 동일한 데이터베이스 스키마
- 동일한 API 엔드포인트
- 동일한 JWT 인증
- 동일한 모델 및 관계

마이그레이션은 점진적으로 수행할 수 있으며, 전환 기간 동안 두 구조가 공존할 수 있습니다.
