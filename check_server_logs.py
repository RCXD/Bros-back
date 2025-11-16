"""
서버 로그 확인용 간단 테스트 - 프로필 이미지 업로드 1건
"""
import requests
from pathlib import Path

BASE_URL = "http://192.168.1.86:8002"

# 1. user1 토큰 획득
print("1. user1 토큰 획득...")
response = requests.post(f"{BASE_URL}/auth/login", json={'username': 'user1', 'password': '1234'})
if response.status_code != 200:
    print(f"❌ 로그인 실패: {response.status_code}")
    exit(1)

token = response.json().get('access_token')
print(f"✓ 토큰 획득: {token[:20]}...\n")

# 2. 프로필 이미지 업로드
print("2. 프로필 이미지 업로드...")
test_image = Path(r"D:\share\dummy data\profile_images\01.jpg")

if not test_image.exists():
    print(f"❌ 테스트 이미지 없음: {test_image}")
    exit(1)

with open(test_image, 'rb') as f:
    files = {'profile_img': ('01.jpg', f, 'image/jpeg')}
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"  업로드: {test_image.name}")
    print(f"  ⏳ 서버 콘솔의 [DEBUG] 로그를 확인하세요...\n")
    
    response = requests.put(f"{BASE_URL}/auth/user", headers=headers, files=files)

print(f"응답 상태 코드: {response.status_code}")

if response.status_code == 200:
    result = response.json()
    print(f"\n응답 데이터:")
    print(f"  profile_img: {result.get('user', {}).get('profile_img')}")
    print(f"\n✅ API 호출 성공")
    print(f"⚠️  서버 콘솔에서 [DEBUG] save_profile_image 로그를 확인하세요")
else:
    print(f"\n❌ API 호출 실패")
    print(f"응답: {response.text}")
