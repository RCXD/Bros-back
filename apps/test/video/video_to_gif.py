"""
영상을 GIF로 변환하는 도구 - 메인 실행 스크립트

필수 라이브러리:
    pip install imageio imageio-ffmpeg pillow
    
시스템 요구사항:
    - FFmpeg 설치 필요
"""

import sys
import argparse
from pathlib import Path

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from apps.test.video.converter import VideoToGifConverter, convert_video_to_gif


def main():
    """메인 함수"""
    
    parser = argparse.ArgumentParser(
        description="영상을 GIF로 변환하는 도구",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예제:
  # 대화형 모드 (권장)
  python video_to_gif.py -i video.mp4
  
  # 명령줄로 직접 실행
  python video_to_gif.py video.mp4 10 5 --fps 10 --output output.gif
  
  # 여러 GIF 한번에 생성
  python video_to_gif.py video.mp4 --batch clips.json
        """
    )
    
    parser.add_argument(
        "video",
        help="입력 영상 파일 경로"
    )
    parser.add_argument(
        "start_time",
        nargs="?",
        type=int,
        default=0,
        help="시작 시간 (초, 기본값: 0)"
    )
    parser.add_argument(
        "duration",
        nargs="?",
        type=int,
        default=5,
        help="GIF 길이 (초, 기본값: 5)"
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=10,
        help="프레임 속도 (기본값: 10)"
    )
    parser.add_argument(
        "--width",
        type=int,
        help="출력 너비 (높이는 자동 계산)"
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=7,
        help="GIF 품질 1-10 (낮을수록 고품질, 기본값: 7)"
    )
    parser.add_argument(
        "--output", "-o",
        help="출력 GIF 파일명"
    )
    parser.add_argument(
        "--output-dir",
        default="./gifs",
        help="GIF 저장 디렉토리 (기본값: ./gifs)"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="대화형 모드"
    )
    parser.add_argument(
        "--batch",
        help="배치 파일 (JSON 형식)"
    )
    
    args = parser.parse_args()
    
    # 비디오 파일 검증
    video_path = Path(args.video)
    if not video_path.exists():
        print(f"❌ 파일을 찾을 수 없음: {args.video}")
        sys.exit(1)
    
    converter = VideoToGifConverter(output_dir=args.output_dir)
    
    try:
        # 대화형 모드
        if args.interactive:
            print("\n" + "=" * 70)
            print("대화형 모드")
            print("=" * 70)
            
            result = converter.interactive_convert(str(video_path))
            print(f"\n✅ 완료: {result}")
        
        # 배치 모드
        elif args.batch:
            import json
            
            with open(args.batch, 'r', encoding='utf-8') as f:
                clips = json.load(f)
            
            print(f"\n📋 배치 변환 시작 ({len(clips)}개 클립)")
            
            results = converter.batch_convert(
                video_path=str(video_path),
                clips=clips,
                output_dir=args.output_dir,
                fps=args.fps,
                width=args.width
            )
            
            print(f"\n✅ 완료! {len(results)}개 GIF 생성됨")
            for result in results:
                print(f"   - {result}")
        
        # 일반 모드
        else:
            print("\n" + "=" * 70)
            print("영상을 GIF로 변환합니다")
            print("=" * 70)
            
            result = converter.convert_to_gif(
                video_path=str(video_path),
                output_path=args.output,
                start_time=args.start_time,
                duration=args.duration,
                fps=args.fps,
                width=args.width,
                quality=args.quality
            )
            
            print(f"\n✅ 완료: {result}")
    
    except Exception as e:
        print(f"\n❌ 에러: {str(e)}")
        sys.exit(1)


def example_batch_convert():
    """배치 변환 예제"""
    print("=" * 70)
    print("배치 변환 예제")
    print("=" * 70)
    
    converter = VideoToGifConverter(output_dir="./clips")
    
    # 변환할 클립 정보
    clips = [
        {
            "start_time": 0,
            "duration": 3,
            "name": "intro"
        },
        {
            "start_time": 5,
            "duration": 5,
            "name": "scene1"
        },
        {
            "start_time": 15,
            "duration": 4,
            "name": "scene2"
        },
        {
            "start_time": 25,
            "duration": 3,
            "name": "outro"
        }
    ]
    
    # 배치 변환
    results = converter.batch_convert(
        video_path="video.mp4",
        clips=clips,
        fps=10,
        width=640
    )
    
    print(f"\n생성된 GIF:")
    for result in results:
        print(f"  ✓ {result}")


def example_interactive():
    """대화형 모드 예제"""
    converter = VideoToGifConverter()
    
    try:
        result = converter.interactive_convert("video.mp4")
        print(f"생성됨: {result}")
    except KeyboardInterrupt:
        print("\n❌ 취소됨")


def example_programmatic():
    """프로그래밍 방식 예제"""
    
    # 예제 1: 기본 사용
    result = convert_video_to_gif(
        video_path="video.mp4",
        start_time=10,
        duration=5,
        fps=10
    )
    print(f"생성됨: {result}")
    
    # 예제 2: 클래스 사용
    converter = VideoToGifConverter(output_dir="./custom_gifs")
    
    result = converter.convert_to_gif(
        video_path="video.mp4",
        output_path="custom.gif",
        start_time=20,
        duration=3,
        fps=12,
        width=800
    )
    
    print(f"생성됨: {result}")


if __name__ == "__main__":
    main()
