import sys
import requests
sys.path.insert(0, '.')

from test.database.gen_user_helper import get_all_user_tokens_from_db
from app import create_app
from pathlib import Path

# 앱 컨텍스트 생성
app = create_app()
app.app_context().push()

# 설정 가져오기
base_url = app.config.get('API_BACKEND_URL', 'http://192.168.1.86:8002')
num_users = app.config.get('NUM_USERS', 10)
num_admins = app.config.get('NUM_ADMINS', 2)

print(f"=== 프로필 이미지 업로드 테스트 ===")
print(f"서버: {base_url}")

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

# 직접 requests로 업로드 (디버깅용)
url = f"{base_url}/auth/user"
headers = {
    'Authorization': f'Bearer {test_user_token}'
}

print("\n3. 프로필 이미지 업로드 시작...")
print(f"   URL: {url}")

with open(test_image, 'rb') as f:
    files = {
        'profile_img': (test_image.name, f, 'image/jpeg')
    }
    
    try:
        response = requests.put(url, headers=headers, files=files, timeout=30)
        
        print(f"\n4. 응답:")
        print(f"   Status Code: {response.status_code}")
        print(f"   Content-Type: {response.headers.get('Content-Type')}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n5. 응답 데이터:")
            print(f"   Message: {result.get('message')}")
            
            user_data = result.get('user', {})
            print(f"\n6. 사용자 정보:")
            print(f"   user_id: {user_data.get('user_id')}")
            print(f"   username: {user_data.get('username')}")
            print(f"   nickname: {user_data.get('nickname')}")
            print(f"   profile_img: {user_data.get('profile_img')}")
            
            # DB 확인
            from apps.app import create_app as create_apps_app
            from apps.auth.models import User
            from apps.post.models import Image
            
            apps_app = create_apps_app('development')
            apps_app.app_context().push()
            
            user_id = user_data.get('user_id')
            user = User.query.filter_by(user_id=user_id).first()
            image = Image.query.filter_by(user_id=user_id, post_id=None).first()
            
            print(f"\n7. DB 검증:")
            print(f"   User.profile_img: {user.profile_img if user else 'User not found'}")
            print(f"   Image record: {'Found' if image else 'Not found'}")
            if image:
                print(f"     - UUID: {image.uuid}")
                print(f"     - Directory: {image.directory}")
                print(f"     - User ID: {image.user_id}")
                print(f"     - Post ID: {image.post_id}")
            
            # 파일 확인
            import os
            print(f"\n8. 파일 시스템 검증:")
            profile_dir = Path("apps/static/profile_images")
            if profile_dir.exists():
                files_found = list(profile_dir.rglob("*.*"))
                print(f"   프로필 이미지 파일 수: {len(files_found)}")
                for f in files_found[:5]:
                    print(f"     - {f.relative_to(profile_dir)}")
            else:
                print(f"   ❌ 디렉토리 없음")
                
        else:
            print(f"\n❌ 업로드 실패")
            print(f"   Response: {response.text[:500]}")
            
    except Exception as e:
        print(f"\n❌ 에러: {e}")
        import traceback
        traceback.print_exc()
