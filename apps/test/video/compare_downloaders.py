"""
여러 YouTube 다운로더 라이브러리 비교 테스트

사용 예제:
    python compare_downloaders.py --show-comparison          # 비교표 출력
    python compare_downloaders.py --library yt-dlp <url> 10 30
    python compare_downloaders.py --library pytube <url> 10 30
    python compare_downloaders.py --test <url> 10 30         # 설치된 모든 라이브러리 테스트
"""

import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from apps.test.video.youtube_downloader import YouTubeDownloader as YtDlpDownloader
from apps.test.video.alternative_downloaders import (
    PytubeDownloader,
    YoutubeDlDownloader,
    PytubefixDownloader,
    PafyDownloader,
    show_comparison,
    DOWNLOADER_COMPARISON,
)


def test_single_library(library: str, url: str, start_time: int, duration: int):
    """단일 라이브러리로 다운로드 테스트"""

    print("\n" + "=" * 80)
    print(f"📌 테스트: {library.upper()}")
    print("=" * 80)

    downloader_classes = {
        "yt-dlp": YtDlpDownloader,
        "pytube": PytubeDownloader,
        "youtube-dl": YoutubeDlDownloader,
        "pytubefix": PytubefixDownloader,
        "pafy": PafyDownloader,
    }

    if library not in downloader_classes:
        print(f"❌ 지원하지 않는 라이브러리: {library}")
        print(f"   지원: {list(downloader_classes.keys())}")
        return False

    try:
        # 라이브러리 정보 출력
        info = DOWNLOADER_COMPARISON.get(library, {})
        if info:
            print(f"평가: {info.get('권장도', 'N/A')}")
            print(f"설치: {info.get('설치', 'N/A')}")

        # 다운로더 생성
        print(f"\n📥 {library} 다운로더 초기화 중...")
        downloader = downloader_classes[library]()

        # 다운로드
        start = time.time()
        print(f"\n📥 다운로드 시작...")
        print(f"   URL: {url}")
        print(f"   시작: {start_time}초")
        print(f"   길이: {duration}초")

        file_path = downloader.download_clip(
            url=url, start_time=start_time, duration=duration
        )

        elapsed = time.time() - start

        # 결과
        file_size = Path(file_path).stat().st_size
        print(f"\n✅ 다운로드 완료!")
        print(f"   파일: {file_path}")
        print(f"   크기: {file_size:,} bytes ({file_size / (1024*1024):.2f} MB)")
        print(f"   시간: {elapsed:.1f}초")

        return True

    except ImportError as e:
        print(f"⚠️  라이브러리 설치 필요")
        print(f"   오류: {str(e)}")
        return False

    except Exception as e:
        print(f"❌ 다운로드 실패")
        print(f"   오류: {str(e)}")
        return False


def test_all_libraries(url: str, start_time: int, duration: int):
    """모든 설치된 라이브러리로 테스트"""

    libraries = ["yt-dlp", "pytube", "pytubefix", "pafy", "youtube-dl"]

    print("\n" + "=" * 80)
    print("🧪 모든 라이브러리 비교 테스트")
    print("=" * 80)

    results = {}
    for lib in libraries:
        success = test_single_library(lib, url, start_time, duration)
        results[lib] = success

    # 결과 요약
    print("\n" + "=" * 80)
    print("📊 테스트 결과 요약")
    print("=" * 80)

    for lib, success in results.items():
        status = "✅ 성공" if success else "❌ 실패"
        print(f"  {lib:12} {status}")


def main():
    parser = argparse.ArgumentParser(
        description="YouTube 다운로더 라이브러리 비교 테스트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예제:
  # 비교표 출력
  python compare_downloaders.py --show-comparison
  
  # 특정 라이브러리 테스트
  python compare_downloaders.py --library yt-dlp <URL> 10 30
  python compare_downloaders.py --library pytube <URL> 10 30
  
  # 설치된 모든 라이브러리 테스트
  python compare_downloaders.py --test <URL> 10 30
        """,
    )

    parser.add_argument(
        "--show-comparison", action="store_true", help="라이브러리 비교표 출력"
    )
    parser.add_argument(
        "--library",
        "-l",
        help="사용할 라이브러리 (yt-dlp, pytube, youtube-dl, pytubefix, pafy)",
    )
    parser.add_argument(
        "--test", "-t", action="store_true", help="모든 라이브러리 테스트"
    )
    parser.add_argument("url", nargs="?", help="YouTube URL")
    parser.add_argument("start", nargs="?", type=int, help="시작 시간 (초)")
    parser.add_argument("duration", nargs="?", type=int, help="영상 길이 (초)")

    args = parser.parse_args()

    # 비교표 출력
    if args.show_comparison:
        show_comparison()
        return

    # URL과 파라미터 확인
    if not args.url or not args.start or not args.duration:
        print("❌ URL, 시작 시간, 길이를 입력해주세요")
        print("   python compare_downloaders.py --show-comparison  (비교표 보기)")
        parser.print_help()
        return

    # 라이브러리별 테스트
    if args.test:
        test_all_libraries(args.url, args.start, args.duration)
    elif args.library:
        test_single_library(args.library, args.url, args.start, args.duration)
    else:
        print("❌ --library 또는 --test 옵션을 지정해주세요")
        parser.print_help()


if __name__ == "__main__":
    main()
