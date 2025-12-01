"""
Verify that /route/analyze endpoint is available.
If not, the Flask server needs to be restarted to pick up the new endpoint.

Run: python verify_route_analyze.py
"""

import requests

BASE_URL = "http://localhost:8002"


def check_endpoint():
    """Check if /route/analyze endpoint exists"""
    print("Checking if /route/analyze endpoint is available...")

    # Try to access the endpoint (should return 401 or 400, not 404)
    try:
        response = requests.post(
            f"{BASE_URL}/route/analyze", json={"points": []}, timeout=5
        )

        if response.status_code == 404:
            print("\n❌ ENDPOINT NOT FOUND (404)")
            print("The /route/analyze endpoint is not available.")
            print("\nACTION REQUIRED:")
            print("1. Stop the Flask server (Ctrl+C in the terminal running it)")
            print("2. Restart with: python apps/app.py --local")
            print("3. Run this script again to verify")
            return False
        else:
            print(f"\n✅ ENDPOINT EXISTS (Status: {response.status_code})")
            print("The /route/analyze endpoint is available!")

            # Show what error we get (should be 400 or 401)
            if response.status_code in [400, 401]:
                print(f"\nExpected error (endpoint working): {response.json()}")

            return True

    except requests.exceptions.ConnectionError:
        print("\n❌ SERVER NOT RUNNING")
        print("Cannot connect to Flask server at http://localhost:8002")
        print("\nACTION REQUIRED:")
        print("Start the server with: python apps/app.py --local")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        return False


if __name__ == "__main__":
    success = check_endpoint()
    exit(0 if success else 1)
