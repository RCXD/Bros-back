"""
Google Street View API 테스트
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env.local
from dotenv import load_dotenv

env_path = project_root / ".env.local"
if env_path.exists():
    load_dotenv(env_path)
    print(f"Loaded environment from: {env_path.absolute()}")
else:
    print(f"Warning: .env.local not found at {env_path.absolute()}")

from apps.roadview.utils import GoogleStreetViewClient, get_roadview_loader_from_env


def test_google_api():
    """구글 스트리트뷰 API 테스트"""
    print("=" * 60)
    print("Google Street View API Test")
    print("=" * 60)

    # Check API key
    google_key = os.getenv("GOOGLE_MAPS_API_KEY")

    if not google_key or google_key == "your-google-api-key-here":
        print("❌ GOOGLE_MAPS_API_KEY is not set!")
        print("Please set it in .env.local file")
        return False

    print(f"✓ API Key found: {google_key[:20]}...{google_key[-4:]}")
    print()

    # Initialize client
    print("Initializing Google Street View client...")
    client = GoogleStreetViewClient(google_key)
    print("✓ Client initialized")
    print()

    # Test location: Seoul City Hall (서울시청)
    test_lat = 37.5665
    test_lng = 126.9780
    test_radius = 50

    print(f"Testing location: {test_lat}, {test_lng}")
    print(f"Radius: {test_radius}m")
    print("Location: Seoul City Hall (서울시청)")
    print()

    try:
        print("Making API request...")
        available, metadata = client.check_availability(test_lat, test_lng, test_radius)

        print()
        print("=" * 60)
        print("RESULT")
        print("=" * 60)

        if available:
            print("✓ Street View Available!")
            print()
            print("Metadata:")
            print(f"  Pano ID: {metadata.get('pano_id')}")
            print(
                f"  Location: ({metadata.get('latitude')}, {metadata.get('longitude')})"
            )
            print(f"  Heading: {metadata.get('heading')}°")
            print(f"  Pitch: {metadata.get('pitch')}°")
            print(f"  Date: {metadata.get('date')}")
            print(f"  Distance from query: {metadata.get('distance'):.2f}m")
            print()

            # Generate image URL
            image_url = client.get_image_url(
                latitude=test_lat,
                longitude=test_lng,
                heading=metadata.get("heading", 0),
                pitch=metadata.get("pitch", 0),
                width=640,
                height=480,
            )
            print(f"Image URL: {image_url[:100]}...")
            print()
            return True
        else:
            print("❌ Street View not available at this location")
            return False

    except Exception as e:
        print()
        print("=" * 60)
        print("ERROR")
        print("=" * 60)
        print(f"❌ API request failed: {str(e)}")
        print()

        # Check if it's an API key error
        if "API key" in str(e) or "authentication" in str(e).lower():
            print("This looks like an API key problem.")
            print("Please check:")
            print("  1. API key is correct")
            print("  2. Street View Static API is enabled in Google Cloud Console")
            print("  3. Billing is set up (required for Google Maps APIs)")

        return False


def test_loader():
    """RoadviewLoader 테스트"""
    print()
    print("=" * 60)
    print("Testing RoadviewLoader")
    print("=" * 60)

    loader = get_roadview_loader_from_env()

    print(f"Google client: {'✓ Available' if loader.google else '❌ NOT AVAILABLE'}")
    print(f"Kakao client: {'✓ Available' if loader.kakao else '❌ NOT AVAILABLE'}")
    print(f"Naver client: {'✓ Available' if loader.naver else '❌ NOT AVAILABLE'}")
    print(f"Priority order: {[p[0] for p in loader.priority]}")
    print()

    if loader.google:
        print("Testing with loader.load_best_roadview()...")
        result = loader.load_best_roadview(37.5665, 126.9780, 50)

        print(f"Success: {result['success']}")
        print(f"Provider: {result['provider']}")
        print(f"Response time: {result['response_time_ms']}ms")

        if result["success"]:
            print("✓ Loader test successful!")
        else:
            print(f"❌ Loader test failed")
            print(f"Errors: {result['errors']}")


if __name__ == "__main__":
    success = test_google_api()

    if success:
        test_loader()

    print()
    print("=" * 60)
    print("Test Complete")
    print("=" * 60)
