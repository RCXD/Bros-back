"""
YouTube 영상 다운로더 - 실제 사용 예제

필수 라이브러리:
    pip install yt-dlp
    pip install ffmpeg-python

시스템 요구사항:
    - FFmpeg 설치 필요 (https://ffmpeg.org/download.html)
"""

import sys
from pathlib import Path

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from apps.test.video.youtube_downloader import YouTubeDownloader, download_youtube_clip


def main():
    """메인 함수 - 실제 사용 예제"""

    print("=" * 70)
    print("YouTube 영상 부분 다운로드")
    print("=" * 70)

    # 예제 1: 간단한 함수 인터페이스 사용
    print("\n[예제 1] 간단한 함수로 다운로드")
    print("-" * 70)

    try:
        # YouTube URL 입력 받기
        url = input("YouTube URL을 입력하세요: ").strip()

        if not url:
            print("❌ URL을 입력해주세요")
            return

        # 시작 시간과 길이 입력
        try:
            start_time = int(input("시작 시간을 입력하세요 (초): "))
            duration = int(input("다운로드할 길이를 입력하세요 (초): "))
        except ValueError:
            print("❌ 숫자를 입력해주세요")
            return

        # 재시도 횟수 입력
        try:
            max_retries_input = input(
                "최대 재시도 횟수 (기본값 5, 권장 10-20): "
            ).strip()
            max_retries = int(max_retries_input) if max_retries_input else 5
            if max_retries <= 0:
                raise ValueError("재시도 횟수는 0보다 커야 합니다")
        except ValueError as e:
            print(f"❌ 입력 오류: {str(e)}")
            return

        # 저장 폴더 입력
        output_dir = input("저장 폴더 (기본값: ./downloads): ").strip()
        if not output_dir:
            output_dir = "./downloads"

        print(f"\n📥 다운로드 시작...")
        print(f"   URL: {url}")
        print(f"   시작: {start_time}초")
        print(f"   길이: {duration}초")
        print(f"   재시도: 최대 {max_retries}회")
        print(f"   저장: {output_dir}")

        # 다운로드
        file_path = download_youtube_clip(
            url=url,
            start_time=start_time,
            duration=duration,
            output_dir=output_dir,
            max_retries=max_retries,
        )

        print(f"\n✅ 다운로드 완료: {file_path}")

    except Exception as e:
        print(f"\n❌ 에러 발생: {str(e)}")
        return


def advanced_example():
    """고급 예제 - 클래스를 직접 사용"""

    print("\n[예제 2] 클래스를 직접 사용하여 여러 클립 다운로드")
    print("-" * 70)

    # 다운로더 인스턴스 생성
    downloader = YouTubeDownloader(output_dir="./clips")

    # 다운로드할 클립 목록
    clips = [
        {
            "url": "https://www.youtube.com/watch?v=example1",
            "start_time": 0,
            "duration": 30,
            "description": "첫 번째 클립",
        },
        {
            "url": "https://www.youtube.com/watch?v=example2",
            "start_time": 60,
            "duration": 45,
            "description": "두 번째 클립",
        },
    ]

    # 각 클립 다운로드
    for clip in clips:
        try:
            print(f"\n📥 {clip['description']} 다운로드 중...")
            file_path = downloader.download_clip(
                url=clip["url"],
                start_time=clip["start_time"],
                duration=clip["duration"],
            )
            print(f"✅ 저장됨: {file_path}")
        except Exception as e:
            print(f"❌ 오류: {str(e)}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="YouTube 영상 부분 다운로드 도구",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예제:
  python downloder.py https://www.youtube.com/watch?v=... 10 30
  python downloder.py https://www.youtube.com/watch?v=... 10 30 --output ./my_clips
  python downloder.py https://www.youtube.com/watch?v=... 10 30 --retries 10
        """,
    )

    parser.add_argument("url", nargs="?", help="YouTube 영상 URL")
    parser.add_argument("start", nargs="?", type=int, help="시작 시간 (초)")
    parser.add_argument("duration", nargs="?", type=int, help="영상 길이 (초)")
    parser.add_argument(
        "--output",
        "-o",
        default="./downloads",
        help="저장 디렉토리 (기본값: ./downloads)",
    )
    parser.add_argument(
        "--retries",
        "-r",
        type=int,
        default=5,
        help="최대 재시도 횟수 (기본값: 5, Rate limit 회피용)",
    )
    parser.add_argument(
        "--interactive", "-i", action="store_true", help="대화형 모드 실행"
    )

    args = parser.parse_args()

    # 대화형 모드
    if args.interactive or not args.url:
        main()
    else:
        # 커맨드라인 인자로 다운로드
        try:
            file_path = download_youtube_clip(
                url=args.url,
                start_time=args.start,
                duration=args.duration,
                output_dir=args.output,
                max_retries=args.retries,
            )
            print(f"\n✅ 완료: {file_path}")
        except Exception as e:
            print(f"\n❌ 에러: {str(e)}")
            sys.exit(1)
