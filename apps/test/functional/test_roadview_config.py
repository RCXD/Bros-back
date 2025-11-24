"""
Roadview API 테스트 스크립트
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from apps.roadview.utils import get_roadview_loader_from_env


def test_api_keys():
    """환경 변수에서 API 키 확인"""
    print("=== API Keys Status ===")

    google_key = os.getenv("GOOGLE_MAPS_API_KEY")
    kakao_key = os.getenv("KAKAO_REST_API_KEY")
    naver_id = os.getenv("NAVER_CLIENT_ID")
    naver_secret = os.getenv("NAVER_CLIENT_SECRET")

    print(
        f"GOOGLE_MAPS_API_KEY: {'✓ SET' if google_key and google_key != 'your-google-api-key-here' else '✗ NOT SET'}"
    )
    if google_key and google_key != "your-google-api-key-here":
        print(f"  Value: {google_key[:10]}...{google_key[-4:]}")

    print(
        f"KAKAO_REST_API_KEY: {'✓ SET' if kakao_key and kakao_key != 'your-kakao-api-key-here' else '✗ NOT SET'}"
    )
    if kakao_key and kakao_key != "your-kakao-api-key-here":
        print(f"  Value: {kakao_key[:10]}...{kakao_key[-4:]}")

    print(
        f"NAVER_CLIENT_ID: {'✓ SET' if naver_id and naver_id != 'your-naver-client-id-here' else '✗ NOT SET'}"
    )
    if naver_id and naver_id != "your-naver-client-id-here":
        print(f"  Value: {naver_id[:10]}...{naver_id[-4:]}")

    print(
        f"NAVER_CLIENT_SECRET: {'✓ SET' if naver_secret and naver_secret != 'your-naver-client-secret-here' else '✗ NOT SET'}"
    )
    if naver_secret and naver_secret != "your-naver-client-secret-here":
        print(f"  Value: {naver_secret[:10]}...{naver_secret[-4:]}")

    print()


def test_roadview_loader():
    """RoadviewLoader 초기화 확인"""
    print("=== Roadview Loader Status ===")

    loader = get_roadview_loader_from_env()

    print(
        f"Google Street View client: {'✓ Available' if loader.google else '✗ NOT AVAILABLE'}"
    )
    print(
        f"Kakao Roadview client: {'✓ Available' if loader.kakao else '✗ NOT AVAILABLE'}"
    )
    print(
        f"Naver Street View client: {'✓ Available' if loader.naver else '✗ NOT AVAILABLE'}"
    )
    print(f"Priority order: {[p[0] for p in loader.priority]}")

    if not loader.priority:
        print("\n⚠️  WARNING: No API clients available!")
        print("Please set at least one of the following API keys:")
        print("  - GOOGLE_MAPS_API_KEY")
        print("  - KAKAO_REST_API_KEY")
        print("  - NAVER_CLIENT_ID + NAVER_CLIENT_SECRET")
        return False

    print(f"\n✓ {len(loader.priority)} provider(s) configured")
    return True


def test_api_availability():
    """실제 API 호출 테스트 (선택적)"""
    print("\n=== API Availability Test ===")

    loader = get_roadview_loader_from_env()

    if not loader.priority:
        print("⚠️  Skipping API test - no clients configured")
        return

    # Test location: Seoul City Hall (서울시청)
    test_lat = 37.5665
    test_lng = 126.9780

    print(f"Testing location: {test_lat}, {test_lng} (Seoul City Hall)")
    print("This will make actual API calls...\n")

    try:
        result = loader.load_best_roadview(test_lat, test_lng, radius=50)

        print(f"Success: {result['success']}")
        print(f"Provider used: {result['provider']}")
        print(f"Providers checked: {result['providers_checked']}")
        print(f"API calls made: {result['api_calls_made']}")
        print(f"Response time: {result['response_time_ms']}ms")

        if result["success"]:
            print(f"\n✓ Roadview available!")
            print(f"  Pano ID: {result['metadata'].get('pano_id')}")
            print(f"  Distance: {result['metadata'].get('distance'):.2f}m")
        else:
            print(f"\n✗ No roadview available")
            if result["errors"]:
                print(f"Errors: {result['errors']}")

    except Exception as e:
        print(f"✗ API test failed: {str(e)}")


if __name__ == "__main__":
    print("Roadview API Configuration Test\n")

    # Test 1: API keys
    test_api_keys()

    # Test 2: Loader initialization
    loader_ok = test_roadview_loader()

    # Test 3: Optional - actual API call
    if loader_ok:
        user_input = input("\nDo you want to test actual API calls? (y/n): ").lower()
        if user_input == "y":
            test_api_availability()
        else:
            print("Skipping API availability test")

    print("\n=== Test Complete ===")
