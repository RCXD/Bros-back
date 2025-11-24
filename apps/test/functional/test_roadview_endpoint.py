"""
/roadview/check 엔드포인트 테스트
"""

import requests
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Load environment
from dotenv import load_dotenv

load_dotenv(project_root / ".env.local")

# Flask app configuration
BASE_URL = "http://127.0.0.1:8002"
ROADVIEW_CHECK_URL = f"{BASE_URL}/roadview/check"

# Test credentials - 실제 테스트 유저 사용
TEST_USERNAME = "user1"
TEST_PASSWORD = "1234"


def get_auth_token():
    """로그인해서 JWT 토큰 가져오기"""
    print("Getting authentication token...")

    login_url = f"{BASE_URL}/auth/login"
    login_data = {"username": TEST_USERNAME, "password": TEST_PASSWORD}

    try:
        response = requests.post(login_url, json=login_data)

        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            print(f"✓ Login successful")
            print(f"  Token: {token[:30]}...")
            return token
        else:
            print(f"❌ Login failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return None

    except Exception as e:
        print(f"❌ Login error: {str(e)}")
        return None


def test_roadview_check(token):
    """roadview check 엔드포인트 테스트"""
    print("\n" + "=" * 60)
    print("Testing /roadview/check endpoint")
    print("=" * 60)

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Test data: Seoul City Hall
    test_data = {
        "latitude": 37.5665,
        "longitude": 126.9780,
        "radius": 50,
        "provider": "google",
    }

    print(f"\nRequest:")
    print(f"  URL: {ROADVIEW_CHECK_URL}")
    print(f"  Location: {test_data['latitude']}, {test_data['longitude']}")
    print(f"  Radius: {test_data['radius']}m")
    print(f"  Preferred provider: {test_data['provider']}")

    try:
        print("\nSending request...")
        response = requests.post(ROADVIEW_CHECK_URL, json=test_data, headers=headers)

        print(f"\nResponse:")
        print(f"  Status code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"\n✓ SUCCESS!")
            print(f"\n  Available: {data.get('available')}")
            print(f"  Provider: {data.get('provider')}")
            print(f"  Roadview ID: {data.get('roadview_id')}")
            print(f"  Cache hit: {data.get('cache_hit')}")
            print(f"  Response time: {data.get('response_time_ms')}ms")

            if data.get("metadata"):
                print(f"\n  Metadata:")
                metadata = data["metadata"]
                print(f"    Pano ID: {metadata.get('pano_id')}")
                print(
                    f"    Location: ({metadata.get('latitude')}, {metadata.get('longitude')})"
                )
                print(f"    Heading: {metadata.get('heading')}°")
                print(f"    Pitch: {metadata.get('pitch')}°")
                print(f"    Date: {metadata.get('image_date')}")
                print(f"    Distance: {metadata.get('distance_from_location')}m")

            print(f"\n  Full response:")
            print(f"  {json.dumps(data, indent=2, ensure_ascii=False)}")

            return True

        elif response.status_code == 404:
            data = response.json()
            print(f"\n  ℹ No roadview available")
            print(f"  Providers checked: {data.get('providers_checked')}")
            print(f"  Errors: {data.get('errors')}")
            print(f"  Response time: {data.get('response_time_ms')}ms")
            return False

        elif response.status_code == 503:
            data = response.json()
            print(f"\n❌ Service unavailable")
            print(f"  Message: {data.get('message')}")
            print(f"  Required keys: {data.get('required_keys')}")
            return False

        else:
            print(f"\n❌ Unexpected status code: {response.status_code}")
            print(f"  Response: {response.text}")
            return False

    except Exception as e:
        print(f"\n❌ Request error: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


def test_without_provider():
    """provider 지정 없이 테스트 (best available 찾기)"""
    print("\n" + "=" * 60)
    print("Testing without specific provider (best available)")
    print("=" * 60)

    token = get_auth_token()
    if not token:
        return False

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    test_data = {
        "latitude": 37.5665,
        "longitude": 126.9780,
        "radius": 50,
        # No provider specified
    }

    print(f"\nRequest (no provider specified):")
    print(f"  Location: {test_data['latitude']}, {test_data['longitude']}")

    try:
        response = requests.post(ROADVIEW_CHECK_URL, json=test_data, headers=headers)

        if response.status_code == 200:
            data = response.json()
            print(f"\n✓ Found roadview!")
            print(f"  Provider chosen: {data.get('provider')}")
            print(f"  Response time: {data.get('response_time_ms')}ms")
            return True
        else:
            print(f"\n  Status: {response.status_code}")
            print(f"  Response: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Roadview Check Endpoint Test")
    print("=" * 60)

    # Test 1: Login and get token
    token = get_auth_token()

    if not token:
        print("\n❌ Cannot proceed without authentication token")
        sys.exit(1)

    # Test 2: Check roadview with Google provider
    success = test_roadview_check(token)

    # Test 3: Check without specifying provider
    test_without_provider()

    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)
