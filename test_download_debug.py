"""
YouTube 다운로드 디버깅 스크립트
다양한 방법으로 다운로드를 시도하고 문제점을 찾습니다.
"""

import sys
from pathlib import Path
import traceback
import io

# Windows 콘솔 인코딩 설정
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# 프로젝트 루트 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 80)
print("YouTube Download Debugging")
print("=" * 80)

# Step 1: 환경 확인
print("\n[Step 1] 환경 확인")
print("-" * 80)

try:
    import yt_dlp

    print(f"✅ yt-dlp 설치됨")
except ImportError as e:
    print(f"❌ yt-dlp 미설치: {e}")
    sys.exit(1)

try:
    import ffmpeg

    print(f"✅ ffmpeg-python 설치됨")
except ImportError:
    print(f"⚠️  ffmpeg-python 미설치 (선택사항)")

try:
    import subprocess

    result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
    if result.returncode == 0:
        first_line = result.stdout.split("\n")[0]
        print(f"✅ FFmpeg 설치됨: {first_line}")
    else:
        print(f"❌ FFmpeg 미설치")
except Exception as e:
    print(f"❌ FFmpeg 확인 실패: {e}")

# Step 2: YouTube 연결 테스트
print("\n[Step 2] YouTube 연결 테스트")
print("-" * 80)

test_urls = [
    "https://www.youtube.com/watch?v=jNQXAC9IVRw",  # 유명한 공개 영상
    "https://youtu.be/jNQXAC9IVRw",  # 단축 URL
]

for url in test_urls:
    try:
        print(f"\n테스트 URL: {url}")

        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            print(f"  ✅ 연결 성공")
            print(f"     제목: {info.get('title', 'N/A')}")
            print(f"     길이: {info.get('duration', 'N/A')}초")
            print(f"     업로더: {info.get('uploader', 'N/A')}")
            break
    except Exception as e:
        print(f"  ❌ 연결 실패: {str(e)}")
        continue

# Step 3: 기본 다운로드 테스트 (부분)
print("\n[Step 3] 기본 다운로드 테스트 (부분)")
print("-" * 80)

test_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
download_dir = Path("downloads/test_debug")
download_dir.mkdir(parents=True, exist_ok=True)

try:
    print(f"URL: {test_url}")
    print(f"저장: {download_dir}")
    print(f"시간: 0-10초")
    print(f"\n다운로드 중...")

    ydl_opts = {
        "format": "best[height<=360]/best",
        "outtmpl": str(download_dir / "test_%(title)s.%(ext)s"),
        "socket_timeout": 30,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        },
        # YouTube 요청 최소화
        "quiet": False,
        "no_warnings": False,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(test_url, download=True)
        video_file = ydl.prepare_filename(info)
        print(f"✅ 다운로드 성공!")
        print(f"   파일: {video_file}")
        print(f"   크기: {Path(video_file).stat().st_size:,} bytes")

        # ffmpeg로 자르기
        print(f"\nffmpeg로 부분 추출 중 (0-10초)...")
        import subprocess

        output_file = download_dir / "test_clip.mp4"
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
            "ultrafast",  # 빠른 인코딩
            "-c:a",
            "aac",
            "-y",
            str(output_file),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ 부분 추출 성공!")
            print(f"   파일: {output_file}")
            print(f"   크기: {output_file.stat().st_size:,} bytes")
        else:
            print(f"❌ 부분 추출 실패:")
            print(result.stderr[-500:] if len(result.stderr) > 500 else result.stderr)

except Exception as e:
    print(f"❌ 다운로드 실패:")
    print(f"오류: {str(e)}")
    print(f"\n상세 정보:")
    traceback.print_exc()

# Step 4: 프로젝트 코드 테스트
print("\n[Step 4] 프로젝트 코드 테스트")
print("-" * 80)

try:
    from apps.test.video.youtube_downloader import YouTubeDownloader

    print("프로젝트의 YouTubeDownloader 테스트 중...")
    downloader = YouTubeDownloader(output_dir="downloads/test_project")

    file_path = downloader.download_clip(
        url=test_url, start_time=0, duration=10, max_retries=3
    )
    print(f"✅ 프로젝트 코드 성공!")
    print(f"   파일: {file_path}")

except Exception as e:
    print(f"❌ 프로젝트 코드 실패:")
    print(f"오류: {str(e)}")
    print(f"\n상세 정보:")
    traceback.print_exc()

print("\n" + "=" * 80)
print("디버깅 완료")
print("=" * 80)
