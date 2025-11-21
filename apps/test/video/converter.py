r"""
🧰 네트워크 공유 영상용 GIF 변환 도구

이 도구는 '\\192.168.1.89\share\movie' 경로에 있는 영상 파일을
직접 선택한 뒤, 일정 구간을 잘라내고 늘어난 화면 영역을 크롭해서
GIF로 변환합니다. 자르는 구간, FPS, 크롭 위치 등은 모두 대화형으로 입력합니다.

사용법:
    1. 네트워크 공유 폴더를 확인합니다.
    2. `python converter.py` 를 실행하면 파일 목록이 표시됩니다.
    3. 번호를 입력하고, 시작 시간/길이/크롭 영역을 입력합니다.
    4. 생성된 GIF는 '\\192.168.1.89\share\movie\gifs'에 저장됩니다.

옵션:
    - 크롭 영역: 왼쪽,위,너비,높이 (예: 120 80 640 360)
    - FPS (기본 10)
    - 출력 너비 (선택 사항; 입력 시 LANCZOS 보간)
    - 반복: loop (0=무한)
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

NETWORK_SHARE_DIR = Path(r"\\192.168.1.89\share\movie")
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".flv"}


class VideoToGifConverter:
    """FFmpeg을 활용한 GIF 변환기"""

    def __init__(
        self,
        output_dir: str = "./gifs",
        share_dir: Optional[str] = None,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.network_share_dir = Path(share_dir) if share_dir else NETWORK_SHARE_DIR

    def convert_to_gif(
        self,
        video_path: str,
        output_path: Optional[str] = None,
        start_time: float = 0,
        duration: float = 5,
        fps: int = 10,
        crop_region: Optional[Tuple[int, int, int, int]] = None,
        scale_width: Optional[int] = None,
        loop: int = 0,
    ) -> str:
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"영상 파일을 찾을 수 없습니다: {video_path}")

        if start_time < 0:
            raise ValueError("시작 시간은 0 이상이어야 합니다")
        if duration <= 0:
            raise ValueError("길이는 0보다 커야 합니다")
        if fps <= 0:
            raise ValueError("FPS는 0보다 커야 합니다")
        if scale_width is not None and scale_width <= 0:
            raise ValueError("출력 너비는 0보다 커야 합니다")

        if output_path is None:
            stem = video_path.stem
            output_name = f"{stem}_{int(start_time)}_{int(duration)}.gif"
            output_path = self.output_dir / output_name
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        filter_string = self._build_filter_string(fps, crop_region, scale_width)
        self._ensure_ffmpeg_available()

        with tempfile.TemporaryDirectory(prefix="gif_palette_") as tmpdir:
            palette_path = Path(tmpdir) / "palette.png"

            self._generate_palette(
                video_path=video_path,
                start_time=start_time,
                duration=duration,
                filter_string=filter_string,
                palette_path=palette_path,
            )

            self._render_gif(
                video_path=video_path,
                start_time=start_time,
                duration=duration,
                filter_string=filter_string,
                palette_path=palette_path,
                output_path=output_path,
                loop=loop,
            )

        print(f"\n✅ GIF 생성 완료")
        print(f"   입력 영상: {video_path}")
        print(f"   시작: {start_time}s, 길이: {duration}s")
        if crop_region:
            print(f"   크롭: {crop_region}")
        if scale_width:
            print(f"   출력 너비: {scale_width}px")
        print(f"   저장 위치: {output_path}")
        print(f"   파일 크기: {self._get_file_size(output_path)}")

        return str(output_path)

    def interactive_network_conversion(self) -> Optional[str]:
        if not self.network_share_dir.exists():
            raise FileNotFoundError(
                f"네트워크 공유 경로를 찾을 수 없습니다: {self.network_share_dir}"
            )

        video_files = self._list_share_videos()
        if not video_files:
            print(
                "📁 영상 파일을 찾을 수 없습니다. '\\192.168.1.89\\share\\movie' 경로를 확인하세요."
            )
            return None

        print("\n\n=== 네트워크 공유 영상 목록 ===")
        for idx, video in enumerate(video_files, 1):
            print(f"[{idx}] {video.name} ({self._safe_duration(video)})")

        choice = input("선택할 파일 번호를 입력하세요: ").strip()
        if not choice.isdigit() or not (1 <= int(choice) <= len(video_files)):
            raise ValueError("올바른 번호를 입력하세요")

        selected_video = video_files[int(choice) - 1]
        try:
            video_duration_value = self._get_video_duration(str(selected_video))
            duration_label = f"{video_duration_value:.1f}s"
        except Exception:
            video_duration_value = None
            duration_label = "알 수 없음"

        print(f"선택된 영상: {selected_video.name} ({duration_label})")

        start_time = float(input("시작 시간(초, 기본 0): ").strip() or "0")
        if start_time < 0:
            raise ValueError("시작 시간은 0 이상이어야 합니다")
        if video_duration_value and start_time >= video_duration_value:
            raise ValueError("시작 시간은 영상 길이보다 작아야 합니다")

        clip_duration = float(input("길이(초, 기본 5): ").strip() or "5")
        if clip_duration <= 0:
            raise ValueError("길이는 0보다 커야 합니다")
        if video_duration_value and (start_time + clip_duration > video_duration_value):
            raise ValueError(
                "시작 시간과 길이의 합은 전체 영상 길이를 넘을 수 없습니다"
            )

        fps = int(input("FPS (기본 10): ").strip() or "10")
        scale_width_input = input("출력 너비(px, 기본 원본 유지): ").strip()
        scale_width = int(scale_width_input) if scale_width_input else None
        crop_region = self._prompt_crop_region()
        loop_input = input("반복 횟수 (0=무한, 기본 0): ").strip()
        loop = int(loop_input) if loop_input else 0
        output_name = (
            input("생성할 GIF 파일명 (ex. clip.gif): ").strip()
            or f"{selected_video.stem}.gif"
        )
        if not output_name.lower().endswith(".gif"):
            output_name += ".gif"
        output_dir = self.network_share_dir / "gifs"
        output_dir.mkdir(parents=True, exist_ok=True)

        return self.convert_to_gif(
            video_path=str(selected_video),
            output_path=str(output_dir / output_name),
            start_time=start_time,
            duration=clip_duration,
            fps=fps,
            crop_region=crop_region,
            scale_width=scale_width,
            loop=loop,
        )

    def _prompt_crop_region(self) -> Optional[Tuple[int, int, int, int]]:
        raw = input(
            "크롭 영역 (왼쪽 위 좌표와 너비/높이, 예: 120 80 640 360, 엔터=전체): "
        ).strip()
        if not raw:
            return None

        parts = re.split(r"[\s,]+", raw)
        if len(parts) != 4:
            raise ValueError("크롭 영역은 4개의 숫자여야 합니다 (x y width height)")

        crop_values = tuple(int(value) for value in parts)
        if any(val < 0 for val in crop_values[:2]) or any(
            val <= 0 for val in crop_values[2:]
        ):
            raise ValueError("크롭 좌표는 0 이상, 너비/높이는 1 이상이어야 합니다")

        return crop_values

    def _list_share_videos(self) -> List[Path]:
        videos = [
            path
            for path in self.network_share_dir.iterdir()
            if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
        ]
        return sorted(videos)

    def _safe_duration(self, video_path: Path) -> str:
        try:
            duration = self._get_video_duration(str(video_path))
            return f"{duration:.1f}s"
        except Exception:
            return "알 수 없음"

    def _build_filter_string(
        self,
        fps: int,
        crop: Optional[Tuple[int, int, int, int]],
        scale_width: Optional[int],
    ) -> str:
        filters = []
        if crop:
            x, y, width, height = crop
            filters.append(f"crop={width}:{height}:{x}:{y}")
        filters.append(f"fps={fps}")
        if scale_width:
            filters.append(f"scale={scale_width}:-1:flags=lanczos")
        return ",".join(filters)

    def _generate_palette(
        self,
        video_path: Path,
        start_time: float,
        duration: float,
        filter_string: str,
        palette_path: Path,
    ) -> None:
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(start_time),
            "-t",
            str(duration),
            "-i",
            str(video_path),
            "-vf",
            f"{filter_string},palettegen",
            str(palette_path),
        ]
        self._run_command(cmd, "palette 생성 실패")

    def _render_gif(
        self,
        video_path: Path,
        start_time: float,
        duration: float,
        filter_string: str,
        palette_path: Path,
        output_path: Path,
        loop: int,
    ) -> None:
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(start_time),
            "-t",
            str(duration),
            "-i",
            str(video_path),
            "-i",
            str(palette_path),
            "-filter_complex",
            f"[0:v]{filter_string}[v];[v][1:v]paletteuse",
            "-loop",
            str(loop),
            str(output_path),
        ]
        self._run_command(cmd, "GIF 생성 실패")

    def _run_command(self, cmd: List[str], message: str) -> None:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"{message}: {result.stderr.strip()}")

    def _ensure_ffmpeg_available(self) -> None:
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True,
                check=True,
            )
        except Exception as exc:
            raise RuntimeError(
                "FFmpeg을 실행할 수 없습니다. https://ffmpeg.org/download.html 에서 설치하세요"
            ) from exc

    def _get_video_duration(self, video_path: str) -> float:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError("영상 길이 정보를 얻을 수 없습니다")
        return float(result.stdout.strip())

    @staticmethod
    def _get_file_size(file_path: Path) -> str:
        size_bytes = file_path.stat().st_size
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"


def main() -> None:
    converter = VideoToGifConverter(
        output_dir=str(Path("gifs")),
        share_dir=str(NETWORK_SHARE_DIR),
    )
    try:
        converter.interactive_network_conversion()
    except Exception as exc:
        print(f"❌ 변환 실패: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
"""
영상을 GIF로 변환하는 모듈

사용법:
    converter = VideoToGifConverter()
    converter.convert_to_gif(
        video_path="path/to/video.mp4",
        output_path="path/to/output.gif",
        start_time=10,      # 시작 시간 (초)
        duration=5,         # GIF 길이 (초)
        fps=10,             # 프레임 속도
        width=640           # 너비 (높이는 자동 계산)
    )
"""

import subprocess
import os
from pathlib import Path
from typing import Optional, Tuple

try:
    import imageio
except ImportError:
    imageio = None


class VideoToGifConverter:
    """영상을 GIF로 변환하는 클래스"""

    def __init__(self, output_dir: str = "./gifs"):
        """
        초기화

        Args:
            output_dir: GIF 저장 디렉토리
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def convert_to_gif(
        self,
        video_path: str,
        output_path: Optional[str] = None,
        start_time: int = 0,
        duration: int = 5,
        fps: int = 10,
        width: Optional[int] = None,
        quality: int = 7,
        loop: int = 0,
    ) -> str:
        """
        영상의 일부를 GIF로 변환

        Args:
            video_path: 입력 영상 경로
            output_path: 출력 GIF 경로 (지정하지 않으면 자동 생성)
            start_time: 시작 시간 (초)
            duration: GIF 길이 (초)
            fps: 프레임 속도 (기본값: 10)
            width: 출력 너비 (높이는 비율에 맞게 자동 계산)
            quality: GIF 품질 (1-10, 낮을수록 고품질, 기본값: 7)
            loop: 반복 횟수 (0=무한반복, 기본값: 0)

        Returns:
            생성된 GIF 파일 경로

        Raises:
            FileNotFoundError: 입력 파일 없음
            ValueError: 잘못된 입력값
            Exception: 변환 실패
        """
        # 입력값 검증
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"영상 파일을 찾을 수 없음: {video_path}")

        if start_time < 0:
            raise ValueError("시작 시간은 0 이상이어야 합니다")
        if duration <= 0:
            raise ValueError("길이는 0보다 커야 합니다")
        if fps <= 0:
            raise ValueError("FPS는 0보다 커야 합니다")
        if not (1 <= quality <= 10):
            raise ValueError("품질은 1-10 사이여야 합니다")

        # 출력 경로 설정
        if output_path is None:
            output_path = self.output_dir / f"clip_{start_time}s_{duration}s.gif"
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        # 임시 프레임 디렉토리
        temp_frames_dir = self.output_dir / f"temp_frames_{start_time}_{duration}"
        temp_frames_dir.mkdir(exist_ok=True)

        try:
            print(f"📺 영상을 GIF로 변환 중...")
            print(f"   입력: {video_path}")
            print(f"   시작: {start_time}초, 길이: {duration}초")
            print(f"   FPS: {fps}, 품질: {quality}/10")

            # Step 1: FFmpeg으로 프레임 추출
            print(f"\n📸 프레임 추출 중...")
            self._extract_frames(video_path, temp_frames_dir, start_time, duration, fps)

            # Step 2: 프레임들로 GIF 생성
            print(f"\n🎬 GIF 생성 중...")
            self._create_gif_from_frames(
                temp_frames_dir, output_path, fps, width, quality, loop
            )

            # Step 3: 임시 파일 정리
            print(f"\n🧹 임시 파일 정리 중...")
            self._cleanup_frames(temp_frames_dir)

            print(f"\n✅ 완료!")
            print(f"   저장 위치: {output_path.absolute()}")
            print(f"   파일 크기: {self._get_file_size(output_path)}")

            return str(output_path)

        except Exception as e:
            # 에러 발생 시 정리
            self._cleanup_frames(temp_frames_dir)
            raise Exception(f"GIF 변환 실패: {str(e)}")

    def batch_convert(
        self,
        video_path: str,
        clips: list,
        output_dir: Optional[str] = None,
        fps: int = 10,
        width: Optional[int] = None,
    ) -> list:
        """
        하나의 영상에서 여러 GIF 생성

        Args:
            video_path: 입력 영상 경로
            clips: 클립 정보 리스트
                [
                    {"start_time": 10, "duration": 5, "name": "clip1"},
                    {"start_time": 30, "duration": 3, "name": "clip2"},
                ]
            output_dir: 저장 디렉토리
            fps: 프레임 속도
            width: 출력 너비

        Returns:
            생성된 GIF 파일 경로 리스트
        """
        if output_dir is None:
            output_dir = self.output_dir

        results = []

        for i, clip in enumerate(clips, 1):
            try:
                start_time = clip.get("start_time", 0)
                duration = clip.get("duration", 5)
                name = clip.get("name", f"clip_{i}")

                output_path = Path(output_dir) / f"{name}.gif"

                print(f"\n[{i}/{len(clips)}] {name} 생성 중...")

                result = self.convert_to_gif(
                    video_path=video_path,
                    output_path=str(output_path),
                    start_time=start_time,
                    duration=duration,
                    fps=fps,
                    width=width,
                )

                results.append(result)

            except Exception as e:
                print(f"❌ {clip.get('name', f'clip_{i}')} 실패: {str(e)}")

        return results

    def interactive_convert(self, video_path: str) -> str:
        """
        대화형으로 GIF 변환

        Args:
            video_path: 입력 영상 경로

        Returns:
            생성된 GIF 파일 경로
        """
        video_path = Path(video_path)

        if not video_path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없음: {video_path}")

        print("\n" + "=" * 70)
        print("영상을 GIF로 변환합니다")
        print("=" * 70)
        print(f"입력 파일: {video_path}")

        # 영상 길이 구하기
        duration = self._get_video_duration(str(video_path))
        print(f"전체 길이: {duration:.1f}초")

        # 사용자 입력
        print("\n📍 GIF로 만들 구간을 선택하세요:")

        try:
            start_time = float(input(f"  시작 시간 (0-{duration:.1f}): "))
            if start_time < 0 or start_time > duration:
                raise ValueError(f"0-{duration:.1f} 범위 내에서 입력하세요")

            max_duration = duration - start_time
            clip_duration = float(input(f"  길이 (1-{max_duration:.1f}초): "))
            if clip_duration <= 0 or clip_duration > max_duration:
                raise ValueError(f"1-{max_duration:.1f}초 범위 내에서 입력하세요")

            fps = int(input("  FPS (기본값 10): ") or "10")
            if fps <= 0:
                raise ValueError("FPS는 0보다 커야 합니다")

            width_input = input("  너비 (기본값: 원본 너비): ").strip()
            width = int(width_input) if width_input else None

            output_name = (
                input("  저장 파일명 (기본값: clip.gif): ").strip() or "clip.gif"
            )
            if not output_name.endswith(".gif"):
                output_name += ".gif"

            output_path = self.output_dir / output_name

            # 변환 실행
            return self.convert_to_gif(
                video_path=str(video_path),
                output_path=str(output_path),
                start_time=int(start_time),
                duration=int(clip_duration),
                fps=fps,
                width=width,
            )

        except ValueError as e:
            print(f"❌ 입력 오류: {str(e)}")
            raise

    def _get_video_duration(self, video_path: str) -> float:
        """FFprobe를 사용하여 영상 길이 구하기"""
        try:
            cmd = [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1:noprint_wrappers=1",
                video_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return float(result.stdout.strip())
        except Exception:
            print("⚠️  영상 길이를 자동으로 감지할 수 없습니다")
            return 0

    def _extract_frames(
        self,
        video_path: Path,
        output_dir: Path,
        start_time: int,
        duration: int,
        fps: int,
    ) -> None:
        """FFmpeg을 사용하여 프레임 추출"""
        cmd = [
            "ffmpeg",
            "-i",
            str(video_path),
            "-ss",
            str(start_time),  # 시작 시간
            "-t",
            str(duration),  # 길이
            "-vf",
            f"fps={fps}",  # FPS
            "-loglevel",
            "error",
            f"{output_dir}/frame_%04d.png",  # 프레임 파일명
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise Exception(f"프레임 추출 실패: {result.stderr}")

        # 추출된 프레임 수 확인
        frames = list(output_dir.glob("frame_*.png"))
        print(f"   ✓ {len(frames)}개 프레임 추출 완료")

    def _create_gif_from_frames(
        self,
        frames_dir: Path,
        output_path: Path,
        fps: int,
        width: Optional[int],
        quality: int,
        loop: int,
    ) -> None:
        """프레임들로 GIF 생성"""
        if imageio is None:
            raise ImportError(
                "imageio 라이브러리가 필요합니다. "
                "설치: pip install imageio imageio-ffmpeg"
            )

        # 프레임 파일 목록 (순서대로)
        frames_list = sorted(frames_dir.glob("frame_*.png"))

        if not frames_list:
            raise Exception("추출된 프레임이 없습니다")

        # 이미지 읽기
        images = []
        duration_per_frame = 1.0 / fps

        for frame_path in frames_list:
            image = imageio.imread(str(frame_path))

            # 너비 조정이 필요하면 처리
            if width:
                height = int(image.shape[0] * width / image.shape[1])
                image = self._resize_image(image, width, height)

            images.append(image)

        # GIF 저장
        imageio.mimsave(
            str(output_path),
            images,
            duration=duration_per_frame,
            loop=loop,
            quality=quality,
        )

        print(f"   ✓ GIF 생성 완료 ({len(images)}프레임)")

    def _resize_image(self, image, width: int, height: int):
        """이미지 크기 조정 (PIL 사용)"""
        try:
            from PIL import Image

            img = Image.fromarray(image)
            img = img.resize((width, height), Image.Resampling.LANCZOS)
            return img
        except ImportError:
            print("⚠️  PIL이 없어서 크기 조정이 불가능합니다")
            print("   설치: pip install pillow")
            return image

    def _cleanup_frames(self, frames_dir: Path) -> None:
        """임시 프레임 디렉토리 삭제"""
        try:
            if frames_dir.exists():
                import shutil

                shutil.rmtree(frames_dir)
                print(f"   ✓ 임시 파일 삭제됨")
        except Exception as e:
            print(f"   ⚠️  임시 파일 삭제 실패: {str(e)}")

    @staticmethod
    def _get_file_size(file_path: Path) -> str:
        """파일 크기를 읽기 좋은 형식으로 반환"""
        size_bytes = file_path.stat().st_size
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"


def convert_video_to_gif(
    video_path: str,
    start_time: int = 0,
    duration: int = 5,
    output_path: Optional[str] = None,
    fps: int = 10,
    width: Optional[int] = None,
    output_dir: str = "./gifs",
) -> str:
    """
    간단한 함수 인터페이스

    Args:
        video_path: 입력 영상 경로
        start_time: 시작 시간 (초)
        duration: GIF 길이 (초)
        output_path: 출력 경로
        fps: 프레임 속도
        width: 출력 너비
        output_dir: 기본 저장 디렉토리

    Returns:
        생성된 GIF 파일 경로
    """
    converter = VideoToGifConverter(output_dir)
    return converter.convert_to_gif(
        video_path=video_path,
        output_path=output_path,
        start_time=start_time,
        duration=duration,
        fps=fps,
        width=width,
    )


if __name__ == "__main__":
    import sys

    print("=" * 70)
    print("영상을 GIF로 변환하는 도구")
    print("=" * 70)

    if len(sys.argv) > 1:
        video_path = sys.argv[1]

        # 명령줄 인자 처리
        try:
            start_time = int(sys.argv[2]) if len(sys.argv) > 2 else 0
            duration = int(sys.argv[3]) if len(sys.argv) > 3 else 5
            fps = int(sys.argv[4]) if len(sys.argv) > 4 else 10

            result = convert_video_to_gif(
                video_path=video_path, start_time=start_time, duration=duration, fps=fps
            )
            print(f"\n✅ 결과: {result}")
        except Exception as e:
            print(f"\n❌ 에러: {str(e)}")
            sys.exit(1)
    else:
        print("\n사용법:")
        print("  python converter.py <영상파일> [시작시간] [길이] [FPS]")
        print("\n예제:")
        print("  python converter.py video.mp4")
        print("  python converter.py video.mp4 10 5 10")
