"""
Test Google Street View Image Download

Google Street View provides both outdoor (roads, streets) and indoor images.
Indoor Street View includes images from buildings, museums, airports, etc.
This test focuses on outdoor road locations.

Run with: python apps/test/functional/test_google_roadview_get_image.py
"""

import requests
import os
from pathlib import Path
from datetime import datetime

BASE_URL = "http://localhost:8002"


def get_test_token():
    """Get JWT token for authentication"""
    login_url = f"{BASE_URL}/auth/login"
    login_data = {"username": "user1", "password": "1234"}
    response = requests.post(login_url, json=login_data)
    if response.status_code == 200:
        return response.json().get("access_token")
    return None


def test_download_roadview_image(token):
    """Test 1: Download Street View image from actual road"""
    print("\nTest 1: Download Roadview Image (Outdoor Road)")

    # Gangnam Station main road (outdoor street view)
    payload = {
        "latitude": 37.4980,
        "longitude": 127.0276,
        "heading": 90,
        "pitch": 0,
        "fov": 90,
        "width": 640,
        "height": 640,
    }

    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.post(
            f"{BASE_URL}/roadview/get-image", json=payload, headers=headers, timeout=20
        )

        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"  Success: {data.get('success')}")
            print(f"  File Path: {data.get('file_path')}")
            print(f"  Filename: {data.get('filename')}")

            metadata = data.get("metadata", {})
            print(f"  File Size: {metadata.get('file_size')} bytes")
            print(f"  Dimensions: {metadata.get('width')}x{metadata.get('height')}")
            print(
                f"  Location: ({metadata.get('latitude')}, {metadata.get('longitude')})"
            )
            print(f"  Heading: {metadata.get('heading')}°")
            print(f"  Timestamp: {metadata.get('timestamp')}")

            # Verify file exists
            file_path = data.get("file_path")
            if file_path and os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                print(f"  File Verified: {file_size} bytes on disk")
                return True
            else:
                print(f"  ERROR: File not found at {file_path}")
                return False
        else:
            error = response.json()
            print(f"  Error: {error.get('message')}")
            return False

    except Exception as e:
        print(f"  Exception: {str(e)}")
        return False


def test_multiple_locations(token):
    """Test 2: Download images from multiple outdoor road locations"""
    print("\nTest 2: Multiple Road Locations (Outdoor)")

    locations = [
        {"name": "Gangnam Main Road", "lat": 37.4980, "lng": 127.0276},
        {"name": "Hongdae Street", "lat": 37.5566, "lng": 126.9233},
        {"name": "Myeongdong Shopping St", "lat": 37.5638, "lng": 126.9826},
        {"name": "Han River Bridge", "lat": 37.5273, "lng": 126.9278},
        {"name": "Gwanghwamun Plaza", "lat": 37.5759, "lng": 126.9768},
    ]

    headers = {"Authorization": f"Bearer {token}"}
    passed = 0

    for loc in locations:
        print(f"  - {loc['name']}", end=": ")

        payload = {
            "latitude": loc["lat"],
            "longitude": loc["lng"],
            "heading": 0,
            "width": 400,
            "height": 400,
        }

        try:
            response = requests.post(
                f"{BASE_URL}/roadview/get-image",
                json=payload,
                headers=headers,
                timeout=20,
            )

            if response.status_code == 200:
                data = response.json()
                filename = data.get("filename")
                file_size = data.get("metadata", {}).get("file_size", 0)
                print(f"{filename} ({file_size} bytes)")
                passed += 1
            else:
                print(f"Error {response.status_code}")

        except Exception as e:
            print(f"Exception")

    print(f"  Result: {passed}/{len(locations)} downloaded")
    return passed > 0


def test_custom_parameters(token):
    """Test 3: Custom heading, pitch, and FOV on actual road"""
    print("\nTest 3: Custom Parameters (Different Angles)")

    test_cases = [
        {"desc": "North facing (0°)", "heading": 0, "pitch": 0, "fov": 90},
        {"desc": "East facing (90°)", "heading": 90, "pitch": 0, "fov": 90},
        {"desc": "South facing (180°)", "heading": 180, "pitch": 0, "fov": 90},
        {"desc": "West facing (270°)", "heading": 270, "pitch": 0, "fov": 90},
        {"desc": "Looking up (30°)", "heading": 0, "pitch": 30, "fov": 120},
        {"desc": "Looking down (-30°)", "heading": 0, "pitch": -30, "fov": 120},
    ]

    headers = {"Authorization": f"Bearer {token}"}
    passed = 0

    # Use Gangnam main road for all angle tests
    for case in test_cases:
        print(f"  - {case['desc']}", end=": ")

        payload = {
            "latitude": 37.4980,
            "longitude": 127.0276,
            "heading": case["heading"],
            "pitch": case["pitch"],
            "fov": case["fov"],
            "width": 320,
            "height": 320,
        }

        try:
            response = requests.post(
                f"{BASE_URL}/roadview/get-image",
                json=payload,
                headers=headers,
                timeout=20,
            )

            if response.status_code == 200:
                data = response.json()
                metadata = data.get("metadata", {})
                print(
                    f"heading={metadata.get('heading')}° pitch={metadata.get('pitch')}° fov={metadata.get('fov')}°"
                )
                passed += 1
            else:
                print(f"Error {response.status_code}")

        except Exception as e:
            print(f"Exception")

    print(f"  Result: {passed}/{len(test_cases)} downloaded")
    return passed > 0


def test_missing_parameters(token):
    """Test 4: Missing required parameters"""
    print("\nTest 4: Missing Parameters")

    payload = {"latitude": 37.5665}  # Missing longitude
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.post(
        f"{BASE_URL}/roadview/get-image", json=payload, headers=headers, timeout=10
    )

    print(f"Status: {response.status_code}")
    if response.status_code == 400:
        print("  Expected 400 - PASSED")
        return True
    else:
        print(f"  Expected 400, got {response.status_code} - FAILED")
        return False


def verify_directory_structure():
    """Verify downloads directory was created"""
    print("\nVerifying Directory Structure:")

    today = datetime.now().strftime("%Y-%m-%d")
    expected_dir = Path("downloads") / "roadview" / today

    if expected_dir.exists():
        files = list(expected_dir.glob("*.jpg"))
        print(f"  Directory: {expected_dir} ✓")
        print(f"  Files: {len(files)} images")

        total_size = sum(f.stat().st_size for f in files)
        print(f"  Total Size: {total_size:,} bytes")
        return True
    else:
        print(f"  Directory not found: {expected_dir}")
        return False


def main():
    print("=" * 70)
    print("Google Street View Image Download Tests")
    print("=" * 70)

    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        print("\nOK: Server is running on port 8002")
    except:
        print("\nERROR: Cannot connect to server on port 8002")
        return

    token = get_test_token()
    if not token:
        print("ERROR: Login failed")
        return
    print("OK: Token obtained")

    print("\nRunning tests...")
    r1 = test_download_roadview_image(token)
    r2 = test_multiple_locations(token)
    r3 = test_custom_parameters(token)
    r4 = test_missing_parameters(token)

    verify_directory_structure()

    print("\n" + "=" * 70)
    print(f"Results: {sum([r1, r2, r3, r4])}/4 tests passed")
    print("=" * 70)


if __name__ == "__main__":
    main()
