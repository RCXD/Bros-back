"""
프로필 이미지 업로드 전체 사용자 테스트
"""
import os
import requests
from pathlib import Path
from apps.app import create_app
from apps.auth.models import User, AccountType
from apps.post.models import Image


# API 서버 URL
BASE_URL = "http://192.168.1.86:8002"

# Flask 앱 생성
apps_app = create_app('development')


def get_user_token(username, password="1234"):
    """사용자 로그인으로 JWT 토큰 획득"""
    url = f"{BASE_URL}/auth/login"
    response = requests.post(url, json={'username': username, 'password': password})
    if response.status_code == 200:
        return response.json().get('access_token')
    return None


print("\n=== 프로필 이미지 업로드 테스트 ===")
print(f"서버: {BASE_URL}\n")

# 1. DB에서 사용자 조회 및 토큰 획득
print("1. 사용자 토큰 획득 중...")
with apps_app.app_context():
    all_users = User.query.all()
    num_regular = User.query.filter_by(account_type=AccountType.USER).count()
    num_admins = User.query.filter_by(account_type=AccountType.ADMIN).count()
    
    print(f"📊 데이터베이스 사용자 현황:")
    print(f"  일반 사용자: {num_regular}명")
    print(f"  관리자: {num_admins}명")
    print(f"  총: {len(all_users)}명\n")

# 토큰 획득
user_tokens = {}
for user in all_users:
    token = get_user_token(user.username)
    if token:
        user_tokens[user.email] = token
        user_type = "👑" if user.account_type == AccountType.ADMIN else "👤"
        print(f"  ✓ {user_type} {user.username} ({user.email})")
    else:
        print(f"  ✗ {user.username} (실패)")

print(f"  총 {len(user_tokens)}/{len(all_users)}개 토큰 획득\n")

if not user_tokens:
    print("❌ 토큰 획득 실패")
    exit(1)


# 2. 테스트 이미지 준비
print("2. 테스트 이미지 준비...")
dummy_profile_dir = Path(r"D:\share\dummy data\profile_images")
test_images = list(dummy_profile_dir.rglob("*.jpg"))

if not test_images:
    print("❌ 테스트 이미지 없음")
    exit(1)

print(f"  {len(test_images)}개 이미지 발견\n")


# 3. 모든 사용자에 대해 프로필 이미지 업로드
print("3. 프로필 이미지 업로드 시작...")
print(f"{'='*70}\n")

success_count = 0
fail_count = 0

for idx, (email, token) in enumerate(user_tokens.items()):
    # Round-robin으로 이미지 할당
    image_path = test_images[idx % len(test_images)]
    
    print(f"[{idx + 1}/{len(user_tokens)}] {email}")
    print(f"  이미지: {image_path.name}")
    
    # API를 통한 프로필 이미지 업로드
    url = f"{BASE_URL}/auth/user"
    headers = {"Authorization": f"Bearer {token}"}
    
    with open(image_path, 'rb') as f:
        files = {'profile_img': (image_path.name, f, 'image/jpeg')}
        response = requests.put(url, headers=headers, files=files)
    
    if response.status_code != 200:
        print(f"  ❌ API 업로드 실패: {response.status_code}")
        print(f"     {response.text}")
        fail_count += 1
        continue
    
    result = response.json()
    returned_uuid = result.get('user', {}).get('profile_img')
    
    if not returned_uuid or returned_uuid == 'static/default_profile.jpg':
        print(f"  ❌ API 응답에 UUID 없음: {returned_uuid}")
        fail_count += 1
        continue
    
    print(f"  ✓ API 업로드 성공 (UUID: {returned_uuid})")
    
    # DB 검증
    with apps_app.app_context():
        user = User.query.filter_by(email=email).first()
        
        if not user:
            print(f"  ❌ DB에서 사용자 찾을 수 없음")
            fail_count += 1
            continue
        
        if user.profile_img == 'static/default_profile.jpg':
            print(f"  ❌ DB에 저장 안됨 (여전히 기본값)")
            fail_count += 1
            continue
        
        if user.profile_img != returned_uuid:
            print(f"  ⚠️  DB UUID 불일치:")
            print(f"     API: {returned_uuid}")
            print(f"     DB:  {user.profile_img}")
        else:
            print(f"  ✓ DB 저장 확인 (UUID: {user.profile_img})")
        
        # Image 레코드 확인
        image_record = Image.query.filter_by(user_id=user.id, post_id=None).first()
        
        if not image_record:
            print(f"  ❌ Image 레코드 없음")
            fail_count += 1
            continue
        
        print(f"  ✓ Image 레코드 확인 (UUID: {image_record.uuid})")
        
        # 파일 시스템 확인
        profile_images_dir = Path("apps/static/profile_images")
        found_files = list(profile_images_dir.rglob(f"{returned_uuid}.*"))
        
        if not found_files:
            print(f"  ❌ 파일 시스템에 파일 없음")
            fail_count += 1
            continue
        
        print(f"  ✓ 파일 확인: {found_files[0].relative_to('apps')}")
        success_count += 1
    
    print()


# 결과 요약
print(f"{'='*70}")
print(f"\n✅ 성공: {success_count}/{len(user_tokens)}")
print(f"❌ 실패: {fail_count}/{len(user_tokens)}")

if success_count == len(user_tokens):
    print("\n🎉 모든 사용자 프로필 이미지 업로드 성공!")
else:
    print(f"\n⚠️  {fail_count}명의 사용자 업로드 실패")
