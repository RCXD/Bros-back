"""
회원가입 시 프로필 이미지 등록 테스트
"""

import requests
import os
from io import BytesIO
from PIL import Image as PILImage

base_url = "http://127.0.0.1:8002"


def create_test_image():
    """테스트용 이미지 생성"""
    img = PILImage.new("RGB", (200, 200), color="blue")
    img_bytes = BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)
    return img_bytes


def test_signup_with_profile_image():
    """프로필 이미지와 함께 회원가입 테스트"""
    print("=" * 60)
    print("회원가입 + 프로필 이미지 등록 테스트")
    print("=" * 60)
    print()

    # 테스트용 사용자 정보
    import time

    timestamp = int(time.time())
    username = f"testuser_{timestamp}"

    # 테스트 이미지 생성
    test_image = create_test_image()

    # 회원가입 요청
    print(f"[테스트 1] 프로필 이미지와 함께 회원가입")
    print(f"POST {base_url}/auth/user")
    print(f"Username: {username}")

    files = {"profile_img": ("test_profile.png", test_image, "image/png")}

    data = {
        "username": username,
        "password": "testpassword123",
        "email": f"{username}@test.com",
        "nickname": f"Test User {timestamp}",
        "address": "서울시 강남구",
        "phone": "010-1234-5678",
    }

    try:
        response = requests.post(
            f"{base_url}/auth/user", files=files, data=data, timeout=10
        )
        print(f"📊 상태 코드: {response.status_code}")

        if response.status_code == 201:
            result = response.json()
            print(f"✅ 회원가입 성공!")
            print(f"📄 응답:")
            print(f"  - Message: {result.get('message')}")
            print(f"  - User ID: {result.get('user', {}).get('user_id')}")
            print(f"  - Username: {result.get('user', {}).get('username')}")
            print(
                f"  - Profile Image UUID: {result.get('user', {}).get('profile_img')}"
            )

            # 프로필 이미지 조회 테스트
            profile_img_uuid = result.get("user", {}).get("profile_img")
            if profile_img_uuid and profile_img_uuid != "default_profile":
                print()
                print(f"[테스트 2] 등록된 프로필 이미지 조회")
                print(f"GET {base_url}/auth/image/{profile_img_uuid}")

                img_response = requests.get(f"{base_url}/auth/image/{profile_img_uuid}")
                print(f"📊 상태 코드: {img_response.status_code}")

                if img_response.status_code == 200:
                    print(
                        f"📄 Content-Type: {img_response.headers.get('Content-Type')}"
                    )
                    print(f"📦 Content-Length: {len(img_response.content):,} bytes")
                    print(f"✅ 프로필 이미지 조회 성공!")
                else:
                    print(f"❌ 프로필 이미지 조회 실패")

            return True
        else:
            print(f"❌ 회원가입 실패")
            print(f"📄 응답: {response.text}")
            return False

    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        return False


def test_signup_without_profile_image():
    """프로필 이미지 없이 회원가입 테스트"""
    print()
    print("=" * 60)
    print("[테스트 3] 프로필 이미지 없이 회원가입")
    print("=" * 60)

    import time

    timestamp = int(time.time())
    username = f"testuser_noimg_{timestamp}"

    print(f"POST {base_url}/auth/user")
    print(f"Username: {username}")

    data = {
        "username": username,
        "password": "testpassword123",
        "email": f"{username}@test.com",
        "nickname": f"Test User No Image",
    }

    try:
        response = requests.post(f"{base_url}/auth/user", data=data, timeout=10)
        print(f"📊 상태 코드: {response.status_code}")

        if response.status_code == 201:
            result = response.json()
            print(f"✅ 회원가입 성공!")
            print(
                f"  - Profile Image: {result.get('user', {}).get('profile_img')} (기본값 사용)"
            )
            return True
        else:
            print(f"❌ 회원가입 실패")
            print(f"📄 응답: {response.text}")
            return False

    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        return False


def main():
    # 서버 연결 확인
    print("🔍 서버 연결 확인 중...")
    try:
        response = requests.get(f"{base_url}/auth/me", timeout=2)
        print(f"✅ 서버가 실행 중입니다!\n")
    except:
        print("❌ 서버에 연결할 수 없습니다.")
        print("   서버를 먼저 실행해주세요: python apps/app.py\n")
        return

    # 테스트 실행
    results = []

    results.append(test_signup_with_profile_image())
    results.append(test_signup_without_profile_image())

    # 결과 요약
    print()
    print("=" * 60)
    print("테스트 결과 요약")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"✅ 통과: {passed}/{total}")
    print(f"❌ 실패: {total - passed}/{total}")

    if passed == total:
        print("\n🎉 모든 테스트를 통과했습니다!")
    else:
        print("\n⚠️  일부 테스트가 실패했습니다.")


if __name__ == "__main__":
    main()
