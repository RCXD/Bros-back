"""
GIF 변환 모듈 통합 테스트
YouTube 다운로더에서 받은 영상을 GIF로 변환하는 전체 워크플로우 테스트
"""

import sys
from pathlib import Path
import json
import time

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from apps.test.video.youtube_downloader import YouTubeDownloader
from apps.test.video.converter import VideoToGifConverter


def test_full_workflow():
    """YouTube 다운로드 → GIF 변환 전체 워크플로우 테스트"""

    print("\n" + "=" * 70)
    print("🎬 YouTube 다운로더 + GIF 변환 통합 테스트")
    print("=" * 70)

    # 테스트용 유튜브 URL (짧은 영상 권장)
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll

    # 다운로드 디렉토리
    download_dir = project_root / "apps/test/video/downloads"
    gif_dir = project_root / "apps/test/video/gifs"

    download_dir.mkdir(exist_ok=True)
    gif_dir.mkdir(exist_ok=True)

    try:
        # Step 1: YouTube 영상 다운로드
        print("\n📥 Step 1: YouTube 영상 다운로드 중...")
        print(f"URL: {test_url}")
        print(f"저장 위치: {download_dir}")

        downloader = YouTubeDownloader(output_dir=str(download_dir))

        # 처음 30초만 다운로드
        video_path = downloader.download_clip(
            url=test_url, start_time=0, duration=30, max_retries=3
        )

        print(f"✅ 다운로드 완료: {video_path}")

        # Step 2: GIF 변환
        print("\n🎨 Step 2: 영상을 GIF로 변환 중...")

        converter = VideoToGifConverter(output_dir=str(gif_dir))

        # 여러 구간을 GIF로 변환
        clips = [
            {"start_time": 0, "duration": 5, "name": "clip_1"},
            {"start_time": 10, "duration": 5, "name": "clip_2"},
            {"start_time": 20, "duration": 5, "name": "clip_3"},
        ]

        results = converter.batch_convert(
            video_path=video_path, clips=clips, fps=10, width=640, quality=6
        )

        print(f"✅ GIF 변환 완료: {len(results)}개 파일 생성")

        # Step 3: 결과 확인
        print("\n📊 Step 3: 결과 확인")
        print(f"영상 파일: {video_path}")
        print(f"생성된 GIF 파일:")

        for result in results:
            gif_path = Path(result)
            if gif_path.exists():
                size_mb = gif_path.stat().st_size / (1024 * 1024)
                print(f"  ✓ {gif_path.name} ({size_mb:.2f} MB)")
            else:
                print(f"  ✗ {gif_path.name} (파일 없음)")

        print("\n" + "=" * 70)
        print("✅ 통합 테스트 완료!")
        print("=" * 70)

        return True

    except Exception as e:
        print(f"\n❌ 테스트 실패: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


def test_gif_conversion_only():
    """GIF 변환만 테스트 (샘플 영상 필요)"""

    print("\n" + "=" * 70)
    print("🎨 GIF 변환 단위 테스트")
    print("=" * 70)

    video_path = project_root / "apps/test/video/sample.mp4"

    if not video_path.exists():
        print(f"⚠️  샘플 영상을 찾을 수 없습니다: {video_path}")
        print("   YouTube에서 먼저 영상을 다운로드하세요.")
        return False

    try:
        converter = VideoToGifConverter(
            output_dir=str(project_root / "apps/test/video/gifs")
        )

        print(f"\n📽️  영상: {video_path}")

        # 테스트 케이스 1: 기본 변환
        print("\n테스트 1: 기본 변환 (0초부터 5초)")
        result1 = converter.convert_to_gif(
            video_path=str(video_path), start_time=0, duration=5, fps=10
        )
        print(f"✅ {result1}")

        # 테스트 케이스 2: 다양한 FPS
        print("\nテスト 2: 높은 FPS (20fps)")
        result2 = converter.convert_to_gif(
            video_path=str(video_path), start_time=5, duration=5, fps=20
        )
        print(f"✅ {result2}")

        # 테스트 케이스 3: 리사이징
        print("\nテスト 3: 리사이징 (너비 480px)")
        result3 = converter.convert_to_gif(
            video_path=str(video_path), start_time=10, duration=3, fps=10, width=480
        )
        print(f"✅ {result3}")

        return True

    except Exception as e:
        print(f"\n❌ 테스트 실패: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


def test_batch_convert():
    """배치 변환 테스트"""

    print("\n" + "=" * 70)
    print("📋 배치 변환 테스트")
    print("=" * 70)

    video_path = project_root / "apps/test/video/sample.mp4"

    if not video_path.exists():
        print(f"⚠️  샘플 영상을 찾을 수 없습니다: {video_path}")
        return False

    try:
        converter = VideoToGifConverter(
            output_dir=str(project_root / "apps/test/video/gifs")
        )

        clips = [
            {"start_time": 0, "duration": 3, "name": "intro", "fps": 10},
            {"start_time": 5, "duration": 4, "name": "main", "fps": 15},
            {"start_time": 10, "duration": 2, "name": "outro", "fps": 12},
        ]

        print(f"📽️  영상: {video_path}")
        print(f"📋 변환할 클립: {len(clips)}개")

        results = converter.batch_convert(
            video_path=str(video_path), clips=clips, width=640
        )

        print(f"\n✅ 배치 변환 완료: {len(results)}개 GIF 생성")

        for result in results:
            gif_path = Path(result)
            if gif_path.exists():
                size_kb = gif_path.stat().st_size / 1024
                print(f"   ✓ {gif_path.name} ({size_kb:.1f} KB)")

        return True

    except Exception as e:
        print(f"\n❌ 테스트 실패: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="GIF 변환 통합 테스트")
    parser.add_argument(
        "--workflow",
        action="store_true",
        help="YouTube 다운로드 + GIF 변환 전체 워크플로우 테스트",
    )
    parser.add_argument("--conversion", action="store_true", help="GIF 변환만 테스트")
    parser.add_argument("--batch", action="store_true", help="배치 변환 테스트")
    parser.add_argument("--all", action="store_true", help="모든 테스트 실행")

    args = parser.parse_args()

    # 기본값: 모든 테스트 실행
    if not any([args.workflow, args.conversion, args.batch, args.all]):
        args.all = True

    results = {}

    if args.all or args.workflow:
        print("\n" + "=" * 70)
        print("테스트 1: 통합 워크플로우")
        print("=" * 70)
        results["workflow"] = test_full_workflow()

    if args.all or args.conversion:
        print("\n" + "=" * 70)
        print("테스트 2: GIF 변환")
        print("=" * 70)
        results["conversion"] = test_gif_conversion_only()

    if args.all or args.batch:
        print("\n" + "=" * 70)
        print("테스트 3: 배치 변환")
        print("=" * 70)
        results["batch"] = test_batch_convert()

    # 최종 결과
    print("\n" + "=" * 70)
    print("📊 테스트 결과 요약")
    print("=" * 70)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")

    all_passed = all(results.values())

    if all_passed:
        print("\n✅ 모든 테스트 통과!")
    else:
        print("\n⚠️  일부 테스트 실패")
        sys.exit(1)
