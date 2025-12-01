"""
Test Route Analysis Endpoint
Tests the new /route/analyze endpoint that integrates OSRM, roadview, and detector services.

Run with: python apps/test/functional/test_route_analysis.py
"""

import requests
import json

BASE_URL = "http://localhost:8002"


def get_test_token():
    """Get JWT token for authentication"""
    login_url = f"{BASE_URL}/auth/login"
    login_data = {"username": "user1", "password": "1234"}
    response = requests.post(login_url, json=login_data)
    if response.status_code == 200:
        return response.json().get("access_token")
    return None


def test_route_analysis_basic():
    """Test basic route analysis with 2 points"""
    print("\n" + "=" * 70)
    print("Test 1: Basic Route Analysis (2 points)")
    print("=" * 70)

    token = get_test_token()
    if not token:
        print("ERROR: Failed to get authentication token")
        return False

    # Simple route in Seoul (Gangnam area)
    payload = {
        "points": [
            {"lat": 37.4980, "lon": 127.0276},  # Gangnam Station
            {"lat": 37.5050, "lon": 127.0300},  # Nearby point
        ],
        "interval_meters": 100,
        "tag": "test_basic",
    }

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    print("\nSending request...")
    print(f"  Start: {payload['points'][0]}")
    print(f"  End: {payload['points'][1]}")
    print(f"  Interval: {payload['interval_meters']}m")

    try:
        response = requests.post(
            f"{BASE_URL}/route/analyze", json=payload, headers=headers, timeout=60
        )

        print(f"\nResponse Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()

            print("\nOSRM Route:")
            osrm = data.get("osrm_route", {})
            print(f"  Distance: {osrm.get('distance')}m")
            print(f"  Duration: {osrm.get('duration')}s")
            print(f"  Legs: {osrm.get('legs_count')}")

            print("\nSummary:")
            summary = data.get("summary", {})
            print(f"  Total Points: {summary.get('total_points')}")
            print(f"  Successful Roadviews: {summary.get('successful_roadviews')}")
            print(f"  Successful Detections: {summary.get('successful_detections')}")
            print(f"  Hazards Created: {summary.get('hazards_created')}")

            print("\nAnalyzed Points (first 3):")
            cache_hits = 0
            for point in data.get("analyzed_points", [])[:3]:
                print(f"  Point {point['index']}:")
                print(f"    Location: ({point['lat']:.6f}, {point['lon']:.6f})")
                print(f"    Heading: {point['heading']:.1f}°")
                print(
                    f"    Roadview: {'OK' if point['roadview_success'] else 'FAILED'}"
                )

                # Show cache status if available
                if point.get("roadview_image"):
                    # Check if roadview was cached (would be in point metadata)
                    # For now, just show it was retrieved
                    pass

                print(
                    f"    Detection: {'OK' if point['detection_success'] else 'FAILED'}"
                )

                if point.get("detection_result"):
                    detections = point["detection_result"].get("detections", [])
                    print(f"    Objects Detected: {len(detections)}")

                if point.get("danger_score") is not None:
                    print(f"    Danger Score: {point['danger_score']:.2f}/10")
                    if point.get("hazard_id"):
                        print(f"    Hazard ID: {point['hazard_id']}")

            # Show hazards summary
            hazards = data.get("hazards", [])
            if hazards:
                print(f"\nHazards Created: {len(hazards)}")
                for hazard in hazards[:3]:
                    print(f"  Hazard #{hazard['hazard_id']}: ")
                    print(f"    Location: ({hazard['lat']:.6f}, {hazard['lon']:.6f})")
                    print(f"    Danger Score: {hazard['danger_score']:.2f}")
                    print(f"    Weight Penalty: {hazard['weight_penalty']:.2f}")

            return True
        else:
            print(f"ERROR: {response.text}")
            return False

    except Exception as e:
        print(f"EXCEPTION: {str(e)}")
        return False


def test_route_analysis_multi_point():
    """Test route analysis with multiple waypoints"""
    print("\n" + "=" * 70)
    print("Test 2: Multi-Point Route Analysis")
    print("=" * 70)

    token = get_test_token()
    if not token:
        print("ERROR: Failed to get authentication token")
        return False

    # Route with 3 waypoints
    payload = {
        "points": [
            {"lat": 37.4980, "lon": 127.0276},  # Gangnam Station
            {"lat": 37.5000, "lon": 127.0280},  # Waypoint 1
            {"lat": 37.5020, "lon": 127.0290},  # Waypoint 2
            {"lat": 37.5050, "lon": 127.0300},  # End
        ],
        "interval_meters": 150,
        "tag": "test_multi",
    }

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    print(f"\nSending request with {len(payload['points'])} waypoints...")

    try:
        response = requests.post(
            f"{BASE_URL}/route/analyze", json=payload, headers=headers, timeout=120
        )

        print(f"\nResponse Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            summary = data.get("summary", {})

            print("\nSummary:")
            print(f"  Total Points: {summary.get('total_points')}")
            print(f"  Successful Roadviews: {summary.get('successful_roadviews')}")
            print(f"  Successful Detections: {summary.get('successful_detections')}")

            success_rate = (
                summary.get("successful_detections", 0) / summary.get("total_points", 1)
            ) * 100
            print(f"  Success Rate: {success_rate:.1f}%")

            return True
        else:
            print(f"ERROR: {response.text}")
            return False

    except Exception as e:
        print(f"EXCEPTION: {str(e)}")
        return False


def test_invalid_input():
    """Test error handling with invalid input"""
    print("\n" + "=" * 70)
    print("Test 3: Invalid Input Handling")
    print("=" * 70)

    token = get_test_token()
    if not token:
        print("ERROR: Failed to get authentication token")
        return False

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Test 1: Only 1 point (should fail)
    print("\n  Test 3.1: Single point (should fail)")
    payload = {"points": [{"lat": 37.4980, "lon": 127.0276}]}

    response = requests.post(
        f"{BASE_URL}/route/analyze", json=payload, headers=headers, timeout=10
    )

    if response.status_code == 400:
        print("    OK: Got expected 400 error")
    else:
        print(f"    FAIL: Expected 400, got {response.status_code}")

    # Test 2: Invalid point format
    print("\n  Test 3.2: Invalid point format (should fail)")
    payload = {
        "points": [{"lat": 37.4980}, {"lat": 37.5050, "lon": 127.0300}]  # Missing lon
    }

    response = requests.post(
        f"{BASE_URL}/route/analyze", json=payload, headers=headers, timeout=10
    )

    if response.status_code == 400:
        print("    OK: Got expected 400 error")
        return True
    else:
        print(f"    FAIL: Expected 400, got {response.status_code}")
        return False


def main():
    print("=" * 70)
    print("Route Analysis Endpoint Tests")
    print("=" * 70)

    # Check server
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        print("\nOK: Server is running on port 8002")
    except:
        print("\nERROR: Cannot connect to server on port 8002")
        print("Make sure the Flask server is running:")
        print("  python apps/app.py")
        return

    # Run tests
    results = []
    results.append(("Basic Route Analysis", test_route_analysis_basic()))
    results.append(("Multi-Point Route", test_route_analysis_multi_point()))
    results.append(("Invalid Input Handling", test_invalid_input()))

    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  {status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")
    print("=" * 70)


if __name__ == "__main__":
    main()
