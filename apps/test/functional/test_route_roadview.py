"""
Test Route-based Street View Image Download
Download Street View images along a route from start to destination

Location: Cheonho-dong, Gangdong-gu, Seoul
Run with: python apps/test/functional/test_route_roadview.py
"""

import requests
import math
from datetime import datetime
from pathlib import Path

BASE_URL = "http://localhost:8002"


def get_test_token():
    """Get JWT token for authentication"""
    login_url = f"{BASE_URL}/auth/login"
    login_data = {"username": "user1", "password": "1234"}
    response = requests.post(login_url, json=login_data)
    if response.status_code == 200:
        return response.json().get("access_token")
    return None


def calculate_bearing(lat1, lon1, lat2, lon2):
    """
    Calculate bearing (heading) from point 1 to point 2
    Returns bearing in degrees (0-360)
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    diff_lon = math.radians(lon2 - lon1)

    x = math.sin(diff_lon) * math.cos(lat2_rad)
    y = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(
        lat2_rad
    ) * math.cos(diff_lon)

    initial_bearing = math.atan2(x, y)
    initial_bearing = math.degrees(initial_bearing)
    bearing = (initial_bearing + 360) % 360

    return bearing


def interpolate_points(start_lat, start_lon, end_lat, end_lon, num_points):
    """
    Generate intermediate points between start and end
    Returns list of (lat, lon, heading) tuples
    """
    points = []

    for i in range(num_points):
        ratio = i / (num_points - 1) if num_points > 1 else 0

        # Linear interpolation
        lat = start_lat + (end_lat - start_lat) * ratio
        lon = start_lon + (end_lon - start_lon) * ratio

        # Calculate heading to next point (or to end if last point)
        if i < num_points - 1:
            next_ratio = (i + 1) / (num_points - 1)
            next_lat = start_lat + (end_lat - start_lat) * next_ratio
            next_lon = start_lon + (end_lon - start_lon) * next_ratio
            heading = calculate_bearing(lat, lon, next_lat, next_lon)
        else:
            # Last point: use same heading as previous
            heading = calculate_bearing(start_lat, start_lon, end_lat, end_lon)

        points.append((lat, lon, heading))

    return points


def download_roadview_at_point(token, lat, lon, heading, index, route_name):
    """Download Street View image at specific point"""
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "latitude": lat,
        "longitude": lon,
        "heading": int(heading),
        "pitch": 0,
        "fov": 90,
        "width": 640,
        "height": 640,
    }

    try:
        response = requests.post(
            f"{BASE_URL}/roadview/get-image", json=payload, headers=headers, timeout=20
        )

        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "index": index,
                "filename": data.get("filename"),
                "file_path": data.get("file_path"),
                "file_size": data.get("metadata", {}).get("file_size", 0),
                "coordinates": (lat, lon),
                "heading": heading,
            }
        else:
            return {
                "success": False,
                "index": index,
                "error": response.json().get("message", "Unknown error"),
            }

    except Exception as e:
        return {"success": False, "index": index, "error": str(e)}


def test_route_roadview(token):
    """Download Street View images along a route in Cheonho-dong"""
    print("\n" + "=" * 70)
    print("Route-based Street View Image Download")
    print("Location: Cheonho-dong, Gangdong-gu, Seoul")
    print("=" * 70)

    # Start point
    start_lat = 37.542377
    start_lon = 127.131134

    # End point
    end_lat = 37.544546
    end_lon = 127.132690

    num_points = 5

    print(f"\nRoute Information:")
    print(f"  Start: ({start_lat}, {start_lon})")
    print(f"  End:   ({end_lat}, {end_lon})")
    print(f"  Points: {num_points} locations along route")

    # Calculate route points
    print(f"\nCalculating {num_points} points along route...")
    points = interpolate_points(start_lat, start_lon, end_lat, end_lon, num_points)

    print("\nRoute Points:")
    for i, (lat, lon, heading) in enumerate(points, 1):
        print(f"  Point {i:2d}: ({lat:.6f}, {lon:.6f}) heading {heading:.1f}°")

    # Download images
    print(f"\nDownloading Street View images...")
    results = []

    for i, (lat, lon, heading) in enumerate(points, 1):
        print(f"  [{i}/{num_points}] ", end="", flush=True)
        result = download_roadview_at_point(
            token, lat, lon, heading, i, "cheonho_route"
        )
        results.append(result)

        if result["success"]:
            print(f"✓ {result['filename']} ({result['file_size']:,} bytes)")
        else:
            print(f"✗ Error: {result['error']}")

    # Summary
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]

    print("\n" + "=" * 70)
    print("Download Summary:")
    print(f"  Total: {len(results)} images")
    print(f"  Success: {len(successful)} images")
    print(f"  Failed: {len(failed)} images")

    if successful:
        total_size = sum(r["file_size"] for r in successful)
        print(f"  Total Size: {total_size:,} bytes")
        print(f"\nSaved to: downloads/roadview/{datetime.now().strftime('%Y-%m-%d')}/")

    if failed:
        print("\nFailed downloads:")
        for r in failed:
            print(f"  Point {r['index']}: {r['error']}")

    print("=" * 70)

    return len(successful) == len(results)


def verify_route_images():
    """Verify downloaded route images"""
    print("\n" + "=" * 70)
    print("Verifying Route Images")
    print("=" * 70)

    today = datetime.now().strftime("%Y-%m-%d")
    download_dir = Path("downloads") / "roadview" / today

    if download_dir.exists():
        images = sorted(download_dir.glob("roadview_*.jpg"))
        print(f"\nTotal images in directory: {len(images)}")

        if images:
            total_size = sum(img.stat().st_size for img in images)
            print(f"Total size: {total_size:,} bytes")

            print(f"\nRecent images (last 10):")
            for img in images[-10:]:
                size = img.stat().st_size
                print(f"  {img.name}: {size:,} bytes")

        return True
    else:
        print(f"Directory not found: {download_dir}")
        return False


def main():
    print("\n" + "=" * 70)
    print("Street View Route Download Test")
    print("Cheonho-dong, Gangdong-gu, Seoul")
    print("=" * 70)

    # Check server
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        print("\n✓ Server is running on port 8002")
    except:
        print("\n✗ Cannot connect to server on port 8002")
        return

    # Get token
    token = get_test_token()
    if not token:
        print("✗ Login failed")
        return
    print("✓ Token obtained")

    # Run test
    success = test_route_roadview(token)

    # Verify files
    verify_route_images()

    if success:
        print("\n✓ All route images downloaded successfully!")
    else:
        print("\n⚠ Some images failed to download")


if __name__ == "__main__":
    main()
