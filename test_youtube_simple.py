"""
YouTube Download Debug - Simple Version
"""

import sys
import subprocess
from pathlib import Path

# Windows 인코딩 설정
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

print("=" * 80)
print("Step 1: Check yt-dlp installation")
print("=" * 80)

# yt-dlp 버전 확인
result = subprocess.run(
    [sys.executable, "-m", "pip", "show", "yt-dlp"], capture_output=True, text=True
)
if result.returncode == 0:
    print("[OK] yt-dlp is installed")
    print(result.stdout)
else:
    print("[ERROR] yt-dlp is not installed")
    print(result.stderr)
    sys.exit(1)

print("\n" + "=" * 80)
print("Step 2: Check FFmpeg installation")
print("=" * 80)

result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
if result.returncode == 0:
    print("[OK] FFmpeg is installed")
    print(result.stdout.split("\n")[0])
else:
    print("[WARNING] FFmpeg not found in PATH")

print("\n" + "=" * 80)
print("Step 3: Test YouTube connection with yt-dlp")
print("=" * 80)

test_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
print(f"Test URL: {test_url}")
print("\nTrying to fetch video info...")

import yt_dlp

try:
    with yt_dlp.YoutubeDL(
        {"quiet": False, "no_warnings": False, "socket_timeout": 30}
    ) as ydl:
        info = ydl.extract_info(test_url, download=False)
        print(f"\n[OK] Connection successful!")
        print(f"    Title: {info.get('title', 'N/A')}")
        print(f"    Duration: {info.get('duration', 'N/A')} seconds")
        print(f"    Uploader: {info.get('uploader', 'N/A')}")
except Exception as e:
    print(f"\n[ERROR] Connection failed!")
    print(f"Error: {str(e)}")
    print("\nTroubleshooting:")
    print("1. Check your internet connection")
    print("2. Try updating yt-dlp: pip install -U yt-dlp")
    print("3. YouTube may have changed their API - check yt-dlp issues on GitHub")
    import traceback

    print("\nFull traceback:")
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 80)
print("Step 4: Test actual download (first 10 seconds)")
print("=" * 80)

download_dir = Path("downloads/test_simple")
download_dir.mkdir(parents=True, exist_ok=True)

try:
    print(f"Downloading to: {download_dir}")
    print("Please wait...")

    ydl_opts = {
        "format": "best[height<=360]/best",
        "outtmpl": str(download_dir / "test_video.%(ext)s"),
        "quiet": False,
        "socket_timeout": 30,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(test_url, download=True)
        video_file = ydl.prepare_filename(info)

        print(f"\n[OK] Download successful!")
        print(f"    File: {video_file}")
        print(f"    Size: {Path(video_file).stat().st_size:,} bytes")

        # Test ffmpeg trimming
        print(f"\nTrimming to 10 seconds with ffmpeg...")
        output_file = download_dir / "test_trimmed.mp4"

        cmd = [
            "ffmpeg",
            "-i",
            video_file,
            "-ss",
            "0",
            "-to",
            "10",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-c:a",
            "aac",
            "-y",
            str(output_file),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"[OK] Trimming successful!")
            print(f"    File: {output_file}")
            print(f"    Size: {output_file.stat().st_size:,} bytes")
        else:
            print(f"[ERROR] Trimming failed!")
            print(result.stderr[-500:] if result.stderr else "No error message")

except Exception as e:
    print(f"\n[ERROR] Download failed!")
    print(f"Error: {str(e)}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 80)
print("All tests passed! Your setup is working correctly.")
print("=" * 80)
