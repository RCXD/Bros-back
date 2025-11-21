"""
테스트용 샘플 영상 생성 도구
FFmpeg를 사용하여 간단한 테스트 영상을 생성합니다.
"""

import subprocess
import sys
from pathlib import Path


def create_test_video(output_path, duration=30, width=1280, height=720, fps=30):
    """
    테스트용 샘플 영상 생성

    Args:
        output_path: 저장할 영상 경로
        duration: 영상 길이 (초)
        width: 너비
        height: 높이
        fps: 프레임 레이트
    """

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"📽️  테스트 영상 생성 중...")
    print(f"   경로: {output_path}")
    print(f"   해상도: {width}x{height}")
    print(f"   길이: {duration}초")
    print(f"   FPS: {fps}")

    # FFmpeg 명령어
    # color 필터로 색상 변화하는 영상 생성
    cmd = [
        "ffmpeg",
        "-f",
        "lavfi",
        "-i",
        f"color=c=blue:s={width}x{height}:d={duration}",
        "-f",
        "lavfi",
        "-i",
        f"sine=f=1000:d={duration}",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(fps),
        "-y",  # 기존 파일 덮어쓰기
        str(output_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        if output_path.exists():
            size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"✅ 영상 생성 완료! ({size_mb:.2f} MB)")
            return str(output_path)
        else:
            print("❌ 영상 생성 실패")
            return None

    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg 에러: {e.stderr}")
        return None
    except FileNotFoundError:
        print("❌ FFmpeg을 찾을 수 없습니다.")
        print("   FFmpeg 설치: https://ffmpeg.org/download.html")
        return None


def create_colorful_test_video(output_path, duration=30):
    """색상이 변화하는 테스트 영상 생성"""

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"🎨 컬러풀한 테스트 영상 생성 중...")

    # 색상이 변하는 영상 생성
    cmd = [
        "ffmpeg",
        "-f",
        "lavfi",
        "-i",
        "color=c=red:s=1280x720:d=10,eq=brightness=0.1",
        "-f",
        "lavfi",
        "-i",
        "color=c=green:s=1280x720:d=10",
        "-f",
        "lavfi",
        "-i",
        "color=c=blue:s=1280x720:d=10",
        "-filter_complex",
        "[0][1][2]concat=n=3:v=1:a=0",
        "-pix_fmt",
        "yuv420p",
        "-y",
        str(output_path),
    ]

    try:
        subprocess.run(cmd, capture_output=True, check=True)
        size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"✅ 영상 생성 완료! ({size_mb:.2f} MB)")
        return str(output_path)
    except Exception as e:
        print(f"❌ 에러: {e}")
        return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="테스트 영상 생성")
    parser.add_argument("--output", "-o", default="sample.mp4", help="저장 경로")
    parser.add_argument("--duration", "-d", type=int, default=30, help="영상 길이 (초)")
    parser.add_argument(
        "--colorful", action="store_true", help="색상이 변하는 영상 생성"
    )

    args = parser.parse_args()

    if args.colorful:
        create_colorful_test_video(args.output, args.duration)
    else:
        create_test_video(args.output, args.duration)
