import sys
sys.path.insert(0, '.')

from test.database.gen_user_helper import get_all_user_tokens_from_db
from test.database.gen_image_helper import ImageAPIUploader
from app import create_app
from pathlib import Path

# 앱 컨텍스트 생성
app = create_app()
app.app_context().push()

# 설정 가져오기
base_url = app.config.get('API_BACKEND_URL', 'http://192.168.1.86:8002')
num_users = app.config.get('NUM_USERS', 10)
num_admins = app.config.get('NUM_ADMINS', 2)

print(f"서버: {base_url}")
print(f"예상 사용자 수: {num_users} + {num_admins}")

# 사용자 토큰 획득
print("\n1. 사용자 토큰 획득 중...")
user_tokens = get_all_user_tokens_from_db(
    app, 
    base_url, 
    expected_users=num_users, 
    expected_admins=num_admins
)

if not user_tokens:
    print("❌ 토큰 획득 실패")
    sys.exit(1)

print(f"✅ {len(user_tokens)}개 토큰 획득")

# 첫 번째 사용자로 테스트
test_user_email = list(user_tokens.keys())[0]
test_user_token = user_tokens[test_user_email]
print(f"\n2. 테스트 사용자: {test_user_email}")

# 테스트 이미지 경로
dummy_profile_dir = Path(app.config.get('DUMMY_PROFILE_IMG_DIR', r"D:\share\dummy data\profile_images"))
test_images = list(dummy_profile_dir.rglob("*.jpg"))[:1]

if not test_images:
    print("❌ 테스트 이미지 없음")
    sys.exit(1)

test_image = test_images[0]
print(f"테스트 이미지: {test_image.name}")

# API Uploader 초기화
api_version = app.config.get('API_VERSION', 'v1')
uploader = ImageAPIUploader(base_url, api_version=api_version)

# 프로필 이미지 업로드
print("\n3. 프로필 이미지 업로드 시작...")
result = uploader.upload_profile_image(
    user_token=test_user_token,
    image_path=str(test_image)
)

print("\n4. 업로드 결과:")
print(f"Result: {result}")

if result:
    print("\n5. 응답 상세:")
    for key, value in result.items():
        print(f"  {key}: {value}")
    
    # 응답 메시지 분석
    message = result.get('message', '')
    print(f"\n6. 메시지 분석:")
    print(f"  원본: '{message}'")
    print(f"  '업데이트' 포함: {'업데이트' in message}")
    print(f"  '수정' 포함: {'수정' in message}")
    print(f"  '성공' 포함: {'성공' in message}")
    print(f"  '완료' 포함: {'완료' in message}")
else:
    print("❌ 업로드 실패 - 응답 없음")
