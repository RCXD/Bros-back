"""
프로필 이미지 삭제 기능 테스트
"""

import os
import sys
import requests
from io import BytesIO
from PIL import Image as PILImage

# Flask 앱 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

BASE_URL = "http://localhost:5000"


def create_test_image():
    """테스트용 이미지 생성"""
    img = PILImage.new("RGB", (100, 100), color="red")
    img_bytes = BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)
    return img_bytes


def test_profile_image_delete():
    """프로필 이미지 삭제 테스트"""

    print("=" * 60)
    print("프로필 이미지 삭제 기능 테스트")
    print("=" * 60)

    # 1. 테스트 계정 생성
    print("\n[1단계] 테스트 계정 생성...")
    test_username = f"test_user_img_del_{os.getpid()}"
    signup_data = {
        "username": test_username,
        "password": "testpass123",
        "email": f"{test_username}@test.com",
        "nickname": "테스트유저",
    }

    # 프로필 이미지와 함께 회원가입
    test_image = create_test_image()
    files = {"profile_img": ("test_profile.jpg", test_image, "image/jpeg")}

    response = requests.post(f"{BASE_URL}/auth/user", data=signup_data, files=files)

    if response.status_code != 201:
        print(f"❌ 회원가입 실패: {response.status_code}")
        print(f"   응답: {response.json()}")
        return False

    print(f"✅ 회원가입 성공")
    user_id = response.json()["user"]["user_id"]
    print(f"   User ID: {user_id}")

    # 2. 로그인하여 토큰 얻기
    print("\n[2단계] 로그인...")
    login_data = {"username": test_username, "password": "testpass123"}

    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)

    if response.status_code != 200:
        print(f"❌ 로그인 실패: {response.status_code}")
        return False

    token = response.json()["access_token"]
    user_data = response.json()["user"]
    initial_profile_img = user_data.get("profile_img")
    print(f"✅ 로그인 성공")
    print(f"   초기 profile_img: {initial_profile_img}")

    headers = {"Authorization": f"Bearer {token}"}

    # 3. 현재 사용자 정보 확인
    print("\n[3단계] 현재 사용자 정보 확인...")
    response = requests.get(f"{BASE_URL}/auth/me", headers=headers)

    if response.status_code == 200:
        user_data = response.json()
        print(f"✅ 사용자 정보 조회 성공")
        print(f"   profile_img: {user_data.get('profile_img')}")

        if user_data.get("profile_img") == "default_profile":
            print("   ⚠️  이미 default_profile 상태입니다")
        else:
            print(f"   ✅ 커스텀 프로필 이미지 설정됨: {user_data.get('profile_img')}")

    # 4. 테스트 케이스 1: 빈 파일로 프로필 이미지 삭제
    print("\n[4단계] 테스트 케이스 1: 빈 파일로 삭제 시도...")
    empty_file = BytesIO(b"")
    files = {"profile_img": ("", empty_file, "image/jpeg")}

    response = requests.put(
        f"{BASE_URL}/auth/user",
        headers=headers,
        data={"nickname": "테스트유저_수정1"},
        files=files,
    )

    print(f"   응답 코드: {response.status_code}")
    if response.status_code == 200:
        user_data = response.json()["user"]
        new_profile_img = user_data.get("profile_img")
        print(f"   수정 후 profile_img: {new_profile_img}")

        if new_profile_img == "default_profile":
            print("   ✅ 성공: default_profile로 변경됨")
        else:
            print(f"   ❌ 실패: 여전히 {new_profile_img}")
    else:
        print(f"   ❌ 요청 실패: {response.json()}")

    # 5. 다시 이미지 업로드
    print("\n[5단계] 다시 프로필 이미지 업로드...")
    test_image2 = create_test_image()
    files = {"profile_img": ("test_profile2.jpg", test_image2, "image/jpeg")}

    response = requests.put(
        f"{BASE_URL}/auth/user",
        headers=headers,
        data={"nickname": "테스트유저_수정2"},
        files=files,
    )

    if response.status_code == 200:
        user_data = response.json()["user"]
        new_profile_img = user_data.get("profile_img")
        print(f"✅ 이미지 업로드 성공")
        print(f"   새 profile_img: {new_profile_img}")

    # 6. 테스트 케이스 2: delete_profile_img 플래그로 삭제
    print("\n[6단계] 테스트 케이스 2: delete_profile_img 플래그로 삭제...")
    response = requests.put(
        f"{BASE_URL}/auth/user",
        headers=headers,
        data={"nickname": "테스트유저_수정3", "delete_profile_img": "true"},
    )

    print(f"   응답 코드: {response.status_code}")
    if response.status_code == 200:
        user_data = response.json()["user"]
        new_profile_img = user_data.get("profile_img")
        print(f"   수정 후 profile_img: {new_profile_img}")

        if new_profile_img == "default_profile":
            print("   ✅ 성공: default_profile로 변경됨")
        else:
            print(f"   ❌ 실패: 여전히 {new_profile_img}")
    else:
        print(f"   ❌ 요청 실패: {response.json()}")

    # 7. 최종 확인
    print("\n[7단계] 최종 사용자 정보 확인...")
    response = requests.get(f"{BASE_URL}/auth/me", headers=headers)

    if response.status_code == 200:
        user_data = response.json()
        print(f"✅ 최종 profile_img: {user_data.get('profile_img')}")

    # 8. 계정 삭제
    print("\n[8단계] 테스트 계정 삭제...")
    response = requests.delete(f"{BASE_URL}/auth/user", headers=headers)

    if response.status_code == 200:
        print("✅ 테스트 계정 삭제 완료")

    print("\n" + "=" * 60)
    print("테스트 완료")
    print("=" * 60)

    return True


if __name__ == "__main__":
    try:
        test_profile_image_delete()
    except Exception as e:
        print(f"\n❌ 테스트 중 오류 발생: {e}")
        import traceback

        traceback.print_exc()
