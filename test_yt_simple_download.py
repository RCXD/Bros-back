"""
YouTube 다운로더 - FFmpeg 없이 전체 영상 다운로드
(부분 다운로드는 FFmpeg 설치 후 사용 가능)

사용법:
    python test_yt_simple_download.py <URL> [output_dir]

예제:
    python test_yt_simple_download.py "https://www.youtube.com/watch?v=jNQXAC9IVRw"
    python test_yt_simple_download.py "https://www.youtube.com/watch?v=jNQXAC9IVRw" "./my_videos"
"""

import sys
import yt_dlp
from pathlib import Path
import time


def download_youtube_video(url: str, output_dir: str = "./downloads") -> str:
    """
    YouTube 영상 전체 다운로드 (FFmpeg 없이)

    Args:
        url: YouTube URL
        output_dir: 저장 디렉토리

    Returns:
        다운로드된 파일 경로
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("YouTube Video Downloader (FFmpeg-free)")
    print("=" * 80)
    print(f"\nURL: {url}")
    print(f"Output: {output_path}")

    # yt-dlp 설정
    ydl_opts = {
        "format": "best[height<=360]/best",  # 저용량 화질 우선
        "outtmpl": str(output_path / "%(title)s_%(id)s.%(ext)s"),
        "quiet": False,
        "no_warnings": False,
        "socket_timeout": 30,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        },
        "progress_hooks": [progress_hook],
    }

    try:
        print("\n[Step 1] Fetching video information...")
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            print(f"  Title: {info.get('title', 'N/A')}")
            print(f"  Duration: {info.get('duration', 'N/A')} seconds")
            print(f"  Uploader: {info.get('uploader', 'N/A')}")

        print("\n[Step 2] Downloading video...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_file = ydl.prepare_filename(info)

        file_size = Path(video_file).stat().st_size
        file_size_mb = file_size / (1024 * 1024)

        print(f"\n[SUCCESS] Download completed!")
        print(f"  File: {video_file}")
        print(f"  Size: {file_size:,} bytes ({file_size_mb:.2f} MB)")

        return video_file

    except Exception as e:
        print(f"\n[ERROR] Download failed!")
        print(f"Error: {str(e)}")

        # 일반적인 오류 및 해결책
        if "429" in str(e) or "rate" in str(e).lower():
            print("\nTroubleshooting:")
            print("  - YouTube is rate-limiting your requests")
            print("  - Try again later or use a VPN")
            print("  - Update yt-dlp: pip install -U yt-dlp")
        elif "unavailable" in str(e).lower():
            print("\nTroubleshooting:")
            print("  - Video may be private, deleted, or region-blocked")
            print("  - Check the URL and try a different video")
        else:
            print("\nTroubleshooting:")
            print("  - Check your internet connection")
            print("  - Try updating yt-dlp: pip install -U yt-dlp")
            print("  - Try a different video")

        raise


def progress_hook(d):
    """진행 상황 표시"""
    if d["status"] == "downloading":
        percent = d.get("_percent_str", "N/A").strip()
        speed = d.get("_speed_str", "N/A").strip()
        eta = d.get("_eta_str", "N/A").strip()
        print(
            f"\r  Progress: {percent} | Speed: {speed} | ETA: {eta}", end="", flush=True
        )
    elif d["status"] == "finished":
        print(f"\n  Download phase finished.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_yt_simple_download.py <URL> [output_dir]")
        print("\nExample:")
        print(
            "  python test_yt_simple_download.py 'https://www.youtube.com/watch?v=jNQXAC9IVRw'"
        )
        print(
            "  python test_yt_simple_download.py 'https://www.youtube.com/watch?v=jNQXAC9IVRw' './my_videos'"
        )
        sys.exit(1)

    url = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "./downloads"

    try:
        file_path = download_youtube_video(url, output_dir)
        print(f"\nDone! Video saved to: {file_path}")
    except Exception as e:
        print(f"\nFailed to download video.")
        sys.exit(1)
