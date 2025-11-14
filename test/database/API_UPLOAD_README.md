# API 기반 이미지 업로드

## 개요

테스트 데이터 생성 시 두 가지 모드를 지원합니다:

### 1. 테스트 환경 (`--use-test-env`)
- **직접 파일 저장 모드**
- 이미지를 `test/uploads/` 폴더에 직접 저장
- 데이터베이스에 Image 레코드 직접 생성
- 로컬 개발 및 테스트에 적합

### 2. 프로덕션 환경 (기본)
- **API 업로드 모드**
- Flask 서버의 엔드포인트를 통해 이미지 업로드
- 실제 서비스와 동일한 방식으로 데이터 생성
- 프로덕션 서버 테스트에 적합

## 사용 방법

### 테스트 환경에서 실행
```powershell
# 직접 파일 저장 (localhost DB, test/uploads)
pytest test/database/generate_all.py -v -s --use-test-env --keep-data
```

### 프로덕션 환경에서 실행
```powershell
# API를 통한 업로드 (192.168.1.86:8000 DB, static/)
pytest test/database/generate_all.py -v -s --keep-data
```

## API 엔드포인트

### 게시글 이미지 업로드
- **엔드포인트**: `PUT /post/edit/<post_id>`
- **인증**: JWT Bearer Token
- **파라미터**:
  - `new_images`: 업로드할 이미지 파일 (multipart/form-data)
- **처리**:
  - 이미지 압축 및 리사이즈 (최대 1024px)
  - UUID 기반 파일명 생성
  - Image 테이블에 레코드 생성
  - `static/post_images/` 폴더에 저장

### 프로필 이미지 업로드
- **엔드포인트**: `PUT /auth/update`
- **인증**: JWT Bearer Token
- **파라미터**:
  - `profile_img`: 업로드할 프로필 이미지 (multipart/form-data)
- **처리**:
  - 이미지 크롭 및 리사이즈 (512x512)
  - UUID 기반 파일명 생성
  - Image 테이블에 레코드 생성 (post_id=NULL)
  - User 테이블의 profile_img 필드 업데이트
  - `static/profile_images/` 폴더에 저장

## 구현 세부사항

### 1. 인증 헬퍼 (`auth_helper.py`)
```python
from test.database.auth_helper import get_all_user_tokens

# 모든 사용자의 JWT 토큰 획득
# username (user1, user2, ...)으로 로그인하여 토큰을 얻고, email을 key로 반환
tokens = get_all_user_tokens("http://192.168.1.86:8000", num_users=10)
# Returns: {'user1@mail.com': 'eyJ0eXAi...', 'user2@mail.com': '...'}

# 개별 사용자 토큰 획득
from test.database.auth_helper import get_user_token
token = get_user_token("http://192.168.1.86:8000", username="user1", password="1234")
```

### 2. 이미지 업로드 헬퍼 (`image_api_helper.py`)
```python
from test.database.image_api_helper import ImageAPIUploader

uploader = ImageAPIUploader("http://192.168.1.86:8000")

# 게시글 이미지 업로드
result = uploader.update_post_images(
    user_token=token,
    post_id=123,
    new_image_paths=['/path/to/image1.png', '/path/to/image2.png']
)

# 프로필 이미지 업로드
result = uploader.upload_profile_image(
    user_token=token,
    image_path='/path/to/profile.png'
)
```

### 3. 환경 감지
```python
# 명령줄 인자로 환경 구분
use_test_env = '--use-test-env' in os.sys.argv

if use_test_env:
    # 직접 파일 저장
    _generate_images_direct(app, dummy_dir, storage_dir)
else:
    # API를 통한 업로드
    _generate_images_via_api(app, dummy_dir)
```

## 장점

### API 업로드 모드의 장점
1. **실제 환경과 동일**: 프로덕션에서 사용하는 것과 동일한 로직으로 이미지 처리
2. **검증 완료**: 서버의 이미지 압축, 리사이즈, 검증 로직 통과
3. **일관성**: 파일 저장 경로, UUID 생성, DB 레코드 생성 모두 실제 코드 사용
4. **통합 테스트**: API 엔드포인트 자체도 함께 테스트

### 직접 저장 모드의 장점
1. **빠른 속도**: HTTP 요청 없이 직접 파일 시스템 접근
2. **오프라인 가능**: 서버 없이도 데이터 생성 가능
3. **디버깅 용이**: 중간 단계 확인 및 오류 추적 쉬움

## 주의사항

### 프로덕션 모드 실행 시
1. **Flask 서버 실행 필수**: `http://192.168.1.86:8000`이 응답해야 함
2. **사용자 계정 존재**: user1~user10, admin1~admin2가 DB에 존재해야 함
   - 로그인 시 **username** (user1, user2, ...) 사용
   - 비밀번호는 기본값 "1234"
3. **네트워크 연결**: 192.168.1.86 서버와 통신 가능해야 함
4. **타임아웃**: 대용량 이미지 업로드 시 타임아웃 발생 가능 (기본 30초)

### 이미지 처리
- 게시글 이미지: 최대 1024px 가로, PNG 형식
- 프로필 이미지: 512x512 정사각형, PNG 형식
- GIF/WebP 애니메이션은 제외
- 이미지 크기에 따라 처리 시간 소요

## 트러블슈팅

### "❌ 로그인 실패" 오류
```
원인: 사용자가 DB에 없거나 username/비밀번호 불일치
해결: 
  1. gen_user.py를 먼저 실행하여 사용자 생성
  2. username이 user1, user2, ... 형식인지 확인
  3. 비밀번호가 "1234"인지 확인
```

### "❌ API 오류: 500" 발생
```
원인: 서버 측 이미지 처리 실패
해결: 이미지 파일 형식 확인, 서버 로그 확인
```

### 업로드 속도가 느림
```
원인: 대용량 이미지를 네트워크로 전송
해결: 
  1. --use-test-env로 로컬 모드 사용
  2. 이미지 파일 크기 줄이기
  3. 네트워크 속도 확인
```

## 예제

### 전체 데이터 생성 (프로덕션)
```powershell
# 1. 서버 실행 확인
curl http://192.168.1.86:8000/

# 2. 데이터 생성
pytest test/database/generate_all.py -v -s --keep-data

# 3. 결과 확인
# - static/profile_images/ 폴더에 프로필 이미지
# - static/post_images/ 폴더에 게시글 이미지
# - images 테이블에 레코드
# - users 테이블의 profile_img 필드 업데이트됨
```

### 개별 스크립트 실행
```powershell
# 프로필 이미지만 업로드 (프로덕션)
pytest test/database/gen_profile_images.py -v -s

# 게시글 이미지만 업로드 (프로덕션)
pytest test/database/gen_images.py -v -s

# 프로필 이미지 (테스트 환경)
pytest test/database/gen_profile_images.py -v -s --use-test-env

# 게시글 이미지 (테스트 환경)
pytest test/database/gen_images.py -v -s --use-test-env
```
