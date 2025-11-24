"""
Google Places API 위치 정보 조회 테스트

서버가 실행 중인 상태에서 테스트합니다.
실행: python apps/test/functional/test_google_location_info.py
"""

import requests

BASE_URL = "http://localhost:8002"


def get_test_token():
    login_url = f"{BASE_URL}/auth/login"
    login_data = {"username": "user1", "password": "1234"}
    response = requests.post(login_url, json=login_data)
    if response.status_code == 200:
        return response.json().get("access_token")
    return None


def test_basic(token):
    print("\nTest 1: Basic Location Info")
    payload = {"latitude": 37.4979, "longitude": 127.0276}
    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.post(
            f"{BASE_URL}/roadview/location-info",
            json=payload,
            headers=headers,
            timeout=10,
        )
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"\n  📍 Basic Info:")
            print(f"     Name: {data.get('name')}")
            print(f"     Address: {data.get('address')}")
            print(f"     Types: {', '.join(data.get('types', []))}")

            print(f"\n  ⭐ Rating & Reviews:")
            print(f"     Rating: {data.get('rating') or 'N/A'}")
            print(f"     Total Reviews: {data.get('reviews_count') or 0}")

            print(f"\n  📞 Contact Info:")
            print(f"     Phone: {data.get('phone') or 'N/A'}")
            print(f"     Website: {data.get('website') or 'N/A'}")

            coords = data.get("coordinates", {})
            if coords:
                print(f"\n  🗺️  Coordinates:")
                print(f"     Lat: {coords.get('lat')}")
                print(f"     Lng: {coords.get('lng')}")

            hours = data.get("opening_hours", {})
            if hours.get("weekday_text"):
                print(f"\n  🕒 Opening Hours:")
                for day in hours["weekday_text"][:3]:
                    print(f"     {day}")
                if len(hours["weekday_text"]) > 3:
                    print(f"     ... and {len(hours['weekday_text']) - 3} more days")

            reviews = data.get("reviews", [])
            if reviews:
                print(f"\n  💬 Recent Reviews ({len(reviews)} shown):")
                for i, review in enumerate(reviews[:2], 1):
                    print(
                        f"     [{i}] {review.get('author')} - {review.get('rating')}⭐"
                    )
                    text = review.get("text", "")
                    print(f"         {text[:60]}{'...' if len(text) > 60 else ''}")
                    print(f"         ({review.get('time')})")
                if len(reviews) > 2:
                    print(f"     ... and {len(reviews) - 2} more reviews")

            photos = data.get("photos", [])
            if photos:
                print(f"\n  📷 Photos ({len(photos)} available):")
                for i, photo in enumerate(photos[:3], 1):
                    print(f"     [{i}] {photo.get('width')}x{photo.get('height')}")
                if len(photos) > 3:
                    print(f"     ... and {len(photos) - 3} more photos")

            return True
        else:
            error = response.json()
            print(f"  Error: {error.get('message')}")
            return False
    except Exception as e:
        print(f"  Exception: {str(e)}")
        return False


def test_missing(token):
    print("\nTest 2: Missing Parameters")
    payload = {"latitude": 37.4979}
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(
        f"{BASE_URL}/roadview/location-info", json=payload, headers=headers, timeout=10
    )
    print(f"Status: {response.status_code}")
    if response.status_code == 400:
        print("  Expected 400 - PASSED")
        return True
    return False


def test_different_locations(token):
    print("\nTest 3: Different Locations")

    test_cases = [
        {"name": "Myeongdong", "lat": 37.5638, "lng": 126.9826},
        {"name": "Hangang Park", "lat": 37.5273, "lng": 126.9278},
        {"name": "Hongdae Station", "lat": 37.5566, "lng": 126.9233},
    ]

    headers = {"Authorization": f"Bearer {token}"}
    passed = 0

    for i, case in enumerate(test_cases, 1):
        print(f"\n  [{i}] {case['name']} ({case['lat']}, {case['lng']})")
        payload = {"latitude": case["lat"], "longitude": case["lng"]}

        try:
            response = requests.post(
                f"{BASE_URL}/roadview/location-info",
                json=payload,
                headers=headers,
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                print(f"      ✓ Found: {data.get('name')}")
                print(f"        Address: {data.get('address')}")
                print(f"        Types: {', '.join(data.get('types', [])[:3])}")
                print(
                    f"        Rating: {data.get('rating') or 'N/A'} ({data.get('reviews_count') or 0} reviews)"
                )
                print(f"        Photos: {len(data.get('photos', []))} available")
                passed += 1
            else:
                print(f"      ✗ Error {response.status_code}")
        except Exception as e:
            print(f"      ✗ Exception: {str(e)}")

    print(f"\n  Result: {passed}/{len(test_cases)} locations passed")
    return passed > 0


def main():
    print("=" * 70)
    print("Google Location Info API Tests")
    print("=" * 70)

    try:
        requests.get(f"{BASE_URL}/", timeout=5)
        print("\nOK: Server is running on port 8002")
    except:
        print("\nERROR: Cannot connect to server")
        return

    token = get_test_token()
    if not token:
        print("ERROR: Login failed")
        return
    print("OK: Token obtained")

    print("\nRunning tests...")
    r1 = test_basic(token)
    r2 = test_missing(token)
    r3 = test_different_locations(token)

    print("\n" + "=" * 70)
    print(f"Results: {sum([r1, r2, r3])}/3 tests passed")
    print("=" * 70)


if __name__ == "__main__":
    main()
