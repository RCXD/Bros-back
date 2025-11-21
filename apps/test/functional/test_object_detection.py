"""
Test Object Detection API with Roadview Images

Sends roadview images to object detection server and displays results
Detection Server: http://192.168.1.79:8888
Run with: python apps/test/functional/test_object_detection.py
"""

import requests
from pathlib import Path
from datetime import datetime

DETECTION_SERVER = "http://192.168.1.79:8888"


def check_server_health():
    """Check if detection server is available"""
    print("\nChecking Detection Server...")
    try:
        response = requests.get(f"{DETECTION_SERVER}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"  Status: {data.get('status')}")
            print(f"  Service: {data.get('service')}")
            print(f"  Version: {data.get('version')}")

            # Display detectable classes
            classes = data.get("endpoints", {}).get("classes", {}).get("list", [])
            print(f"\n  Detectable Classes ({len(classes)}):")
            for i, cls in enumerate(classes, 1):
                print(f"    {i:2d}. {cls}")

            return True
        else:
            print(f"  Error: Status {response.status_code}")
            return False
    except Exception as e:
        print(f"  Error: {str(e)}")
        return False


def attach_model():
    """Load detection model"""
    print("\nAttaching Detection Model...")
    try:
        response = requests.get(f"{DETECTION_SERVER}/attach-model", timeout=30)
        if response.status_code == 200:
            data = response.json()
            print(f"  Response: {data.get('message', data)}")
            return True
        elif response.status_code == 404:
            # Model already attached
            print(f"  Response: {response.text}")
            print(f"  Model is already loaded")
            return True
        else:
            print(f"  Error: Status {response.status_code}")
            return False
    except Exception as e:
        print(f"  Error: {str(e)}")
        return False


def detect_objects_in_image(image_path, save_result=True):
    """Send image to detection server and get results"""
    try:
        with open(image_path, "rb") as f:
            files = {"files": (image_path.name, f, "image/jpeg")}
            response = requests.post(
                f"{DETECTION_SERVER}/detect", files=files, timeout=30
            )

        if response.status_code == 200:
            data = response.json()
            result_data = {"success": True, "data": data}

            # Draw detection result if requested
            if save_result:
                # Get detections for this image
                results = data.get("results", {})
                detections = results.get(image_path.name, [])

                if detections:
                    result_image_path = draw_detection_result(image_path, detections)
                    result_data["result_image"] = result_image_path

            return result_data
        else:
            return {"success": False, "error": f"Status {response.status_code}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def draw_detection_result(image_path, detections):
    """Draw bounding boxes on image and save result"""
    try:
        from PIL import Image, ImageDraw, ImageFont

        # Open original image
        img = Image.open(image_path)
        draw = ImageDraw.Draw(img)

        # Define colors for different classes
        colors = {
            "Person": "#FF0000",  # Red
            "Traffic cone": "#FFA500",  # Orange
            "Manhole": "#FFFF00",  # Yellow
            "Garbage bag & sacks": "#00FF00",  # Green
            "Pothole on road": "#0000FF",  # Blue
            "Box": "#FF00FF",  # Magenta
            "Stones on road": "#00FFFF",  # Cyan
            "Filled pothole": "#800080",  # Purple
            "Animals(Dolls)": "#FFC0CB",  # Pink
            "Construction signs & Parking prohibited board": "#A52A2A",  # Brown
        }

        # Draw each detection
        for detection in detections:
            label = detection.get("label", "Unknown")
            confidence = detection.get("confidence", 0)
            box = detection.get("box", [])

            if len(box) == 4:
                x1, y1, x2, y2 = box
                color = colors.get(label, "#FFFFFF")

                # Draw bounding box
                draw.rectangle([x1, y1, x2, y2], outline=color, width=3)

                # Draw label background
                text = f"{label} {confidence:.0%}"
                # Use default font
                bbox = draw.textbbox((x1, y1), text)
                draw.rectangle(
                    [bbox[0] - 2, bbox[1] - 2, bbox[2] + 2, bbox[3] + 2], fill=color
                )
                draw.text((x1, y1), text, fill="#000000")

        # Save result image
        today = datetime.now().strftime("%Y-%m-%d")
        save_dir = Path("downloads") / "detection" / today
        save_dir.mkdir(parents=True, exist_ok=True)

        filename = Path(image_path).name
        result_filename = f"detected_{filename}"
        save_path = save_dir / result_filename

        img.save(save_path, "JPEG", quality=95)
        return str(save_path)

    except Exception as e:
        print(f"  Warning: Could not draw result image: {str(e)}")
        return None


def test_roadview_detection():
    """Test object detection on roadview images"""
    print("\n" + "=" * 70)
    print("Object Detection Test on Roadview Images")
    print("=" * 70)

    # Image files to test
    today = datetime.now().strftime("%Y-%m-%d")
    download_dir = Path("downloads") / "roadview" / today

    image_files = [
        "roadview_20251121_001010.jpg",
        "roadview_20251121_001013.jpg",
        "roadview_20251121_001016.jpg",
        "roadview_20251121_001019.jpg",
        "roadview_20251121_001022.jpg",
    ]

    print(f"\nLooking for images in: {download_dir}")

    # Check if images exist
    existing_images = []
    for filename in image_files:
        image_path = download_dir / filename
        if image_path.exists():
            existing_images.append(image_path)
            print(f"  ✓ {filename} ({image_path.stat().st_size:,} bytes)")
        else:
            print(f"  ✗ {filename} (not found)")

    if not existing_images:
        print("\nNo images found! Please run test_route_roadview.py first.")
        return False

    print(f"\nFound {len(existing_images)} images")

    # Process each image
    print("\n" + "=" * 70)
    print("Detection Results")
    print("=" * 70)

    all_detections = []

    for i, image_path in enumerate(existing_images, 1):
        print(f"\n[{i}/{len(existing_images)}] Processing: {image_path.name}")
        print("-" * 70)

        result = detect_objects_in_image(image_path, save_result=True)

        if result["success"]:
            data = result["data"]
            status = data.get("status", "Unknown")
            results = data.get("results", {})

            print(f"  Status: {status}")

            # Show result image path if saved
            if result.get("result_image"):
                print(f"  Result Image: {result['result_image']}")

            # Get detections for this image
            image_detections = results.get(image_path.name, [])

            if image_detections:
                print(f"  Detected Objects: {len(image_detections)}")
                for j, detection in enumerate(image_detections, 1):
                    label = detection.get("label", "Unknown")
                    confidence = detection.get("confidence", 0)
                    box = detection.get("box", [])

                    print(f"    [{j}] {label}")
                    print(f"        Confidence: {confidence:.2%}")
                    print(f"        Bounding Box: {box}")

                all_detections.extend(image_detections)
            else:
                print(f"  No objects detected")
        else:
            print(f"  Error: {result['error']}")

    # Summary
    print("\n" + "=" * 70)
    print("Detection Summary")
    print("=" * 70)
    print(f"  Images Processed: {len(existing_images)}")
    print(f"  Total Objects Detected: {len(all_detections)}")

    if all_detections:
        # Count by label
        label_counts = {}
        for detection in all_detections:
            label = detection.get("label", "Unknown")
            label_counts[label] = label_counts.get(label, 0) + 1

        print(f"\n  Object Types:")
        for label, count in sorted(
            label_counts.items(), key=lambda x: x[1], reverse=True
        ):
            print(f"    - {label}: {count}")

        # Average confidence
        avg_confidence = sum(d.get("confidence", 0) for d in all_detections) / len(
            all_detections
        )
        print(f"\n  Average Confidence: {avg_confidence:.2%}")

    # Check saved result images
    today = datetime.now().strftime("%Y-%m-%d")
    result_dir = Path("downloads") / "detection" / today
    if result_dir.exists():
        result_images = list(result_dir.glob("*.jpg"))
        print(f"\n  Result Images Saved: {len(result_images)}")
        print(f"  Save Location: {result_dir}")

    print("=" * 70)

    return True


def main():
    print("=" * 70)
    print("Object Detection API Test")
    print("Server: http://192.168.1.79:8888")
    print("=" * 70)

    # Check server
    if not check_server_health():
        print("\nError: Detection server is not available")
        return

    # Attach model
    if not attach_model():
        print("\nError: Failed to attach detection model")
        return

    # Run detection test
    test_roadview_detection()

    print("\n✓ Test completed!")


if __name__ == "__main__":
    main()
