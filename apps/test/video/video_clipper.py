"""
지정 시간 구간을 기준으로 영상을 자르는 도구
시스템 요구사항 : ffmpeg 설치 필요, 시스템 환경 변수의 path에 ffmpeg 경로 추가 필요
"""

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

FFMPEG_CMD = "ffmpeg"
FFPROBE_CMD = "ffprobe"
VIDEO_STORAGE_DIR = Path(r"C:\Users\lst24\Downloads")


def _normalize_extension(ext: Optional[str], fallback: str) -> str:
    normalized_fallback = (
        fallback if fallback.startswith(".") else f".{fallback.lstrip('.')}"
    )
    if not ext:
        return normalized_fallback
    return ext if ext.startswith(".") else f".{ext}"


def _run_command(arguments: List[str], error_hint: str) -> None:
    result = subprocess.run(
        arguments, capture_output=True, text=True, encoding="utf-8", errors="ignore"
    )
    if result.returncode != 0:
        raise RuntimeError(f"{error_hint}: {result.stderr.strip()}")


def _format_time(value: float) -> str:
    return f"{value:.3f}"


def _ensure_tool_available(tool: str) -> None:
    try:
        subprocess.run([tool, "-version"], capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"{tool} 명령을 실행할 수 없습니다.") from exc
    except FileNotFoundError as exc:
        raise RuntimeError(f"{tool}을 찾을 수 없습니다.") from exc


def _get_duration(path: Path) -> float:
    cmd = [
        FFPROBE_CMD,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError("영상 길이를 읽을 수 없습니다")
    return float(result.stdout.strip())


@dataclass
class ClipResult:
    output_path: Path
    duration: float


def clip_video(
    video_path: str,
    start: float,
    end: float,
    output_path: Optional[str] = None,
    codec: str = "copy",
    extra_args: Optional[List[str]] = None,
    overwrite: bool = True,
    default_output_dir: Optional[Path] = None,
    scale_width: Optional[int] = None,
    quality: Optional[int] = None,
    output_ext: Optional[str] = None,
) -> ClipResult:
    path = Path(video_path)
    if not path.is_absolute():
        path = VIDEO_STORAGE_DIR / path
    if not path.exists():
        raise FileNotFoundError(f"입력 영상을 찾을 수 없습니다: {path}")

    if start < 0 or end <= start:
        raise ValueError("시작 시간은 0 이상이고 종료 시간은 시작 시간보다 커야 합니다")

    extension = _normalize_extension(output_ext, path.suffix)
    duration = end - start

    if scale_width and codec == "copy":
        raise ValueError("스케일을 적용하려면 재인코딩 설정(--reencode)을 사용하세요")
    if quality is not None and codec == "copy":
        raise ValueError("CRF 화질은 재인코딩 모드에서만 설정 가능합니다")

    if output_path:
        output_path_candidate = Path(output_path)
        if output_path_candidate.is_dir():
            output_path_candidate.mkdir(parents=True, exist_ok=True)
            final_output = (
                output_path_candidate
                / f"{path.stem}_{int(start)}-{int(end)}{extension}"
            )
        else:
            output_path_candidate.parent.mkdir(parents=True, exist_ok=True)
            final_output = (
                output_path_candidate.with_suffix(extension)
                if output_ext
                else output_path_candidate
            )
    else:
        target_dir = default_output_dir if default_output_dir else path.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        final_output = target_dir / f"{path.stem}_{int(start)}-{int(end)}{extension}"

    _ensure_tool_available(FFMPEG_CMD)
    _ensure_tool_available(FFPROBE_CMD)

    flags = ["-y"] if overwrite else ["-n"]
    cmd = [
        FFMPEG_CMD,
        *flags,
        "-ss",
        _format_time(start),
        "-i",
        str(path),
        "-t",
        _format_time(duration),
        "-c",
        codec,
    ]
    if quality is not None:
        cmd += ["-crf", str(quality)]
    if scale_width:
        cmd += ["-vf", f"scale={scale_width}:-2"]
    if extra_args:
        cmd.extend(extra_args)
    cmd.append(str(final_output))

    _run_command(cmd, "비디오 클립 생성 실패")

    actual_duration = _get_duration(final_output)
    if abs(actual_duration - duration) > 0.3:
        raise RuntimeError(
            f"생성된 클립 길이({actual_duration:.2f}s)가 기대({duration:.2f}s)와 다릅니다"
        )

    return ClipResult(output_path=final_output, duration=actual_duration)


def _resolve_video_path(raw: str) -> Path:
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = VIDEO_STORAGE_DIR / candidate
    return candidate


def _prompt_for_float(
    prompt: str, min_value: Optional[float] = None, max_value: Optional[float] = None
) -> float:
    while True:
        raw = input(prompt).strip()
        try:
            value = float(raw)
        except ValueError:
            print("숫자를 입력하세요.")
            continue
        if min_value is not None and value < min_value:
            print(f"{min_value} 이상을 입력하세요.")
            continue
        if max_value is not None and value > max_value:
            print(f"{max_value} 이하를 입력하세요.")
            continue
        return value


def interactive_clip(
    codec: str = "copy",
    extra_args: Optional[List[str]] = None,
    overwrite: bool = True,
    scale_width: Optional[int] = None,
    quality: Optional[int] = None,
    output_ext: Optional[str] = None,
) -> ClipResult:
    print("\n=== 대화형 클리핑 모드 ===")
    while True:
        raw_path = input(
            "비디오 파일 경로 (공유 폴더 기준 또는 전체 경로, 예: sample.mp4): "
        ).strip()
        if not raw_path:
            print("경로를 입력해야 합니다.")
            continue
        video_path = _resolve_video_path(raw_path)
        if not video_path.exists():
            print(f"파일을 찾을 수 없습니다: {video_path}")
            continue
        break

    total_duration = _get_duration(video_path)
    print(f"전체 영상 길이: {total_duration:.2f}s")

    while True:
        start = _prompt_for_float("시작 시간 (초): ", min_value=0.0)
        if start >= total_duration:
            print("시작 시간은 전체 영상 길이보다 작아야 합니다.")
            continue
        break

    while True:
        end = _prompt_for_float(
            "종료 시간 (초): ", min_value=start + 0.01, max_value=total_duration
        )
        if end <= start:
            print("종료 시간은 시작 시간보다 커야 합니다.")
            continue
        break

    default_output_dir = video_path.parent / "output"
    print(f"출력 디렉터리 기본값: {default_output_dir}")
    output_raw = input("출력 파일 경로 (엔터=기본): ").strip()
    output_path = output_raw if output_raw else None

    scale_raw = input("출력 너비(px, 엔터=기본): ").strip()
    if scale_raw:
        try:
            scale_width = int(scale_raw)
        except ValueError:
            print("숫자로 입력하세요. 무시하고 기존값 유지합니다.")

    quality_raw = input("화질(CRF 0-51, 엔터=기본): ").strip()
    if quality_raw:
        try:
            quality = int(quality_raw)
        except ValueError:
            print("정수를 입력하세요. 무시하고 기존값 유지합니다.")

    ext_raw = input("출력 확장자 (예: mp4, gif, 엔터=입력과 동일): ").strip()
    if ext_raw:
        output_ext = ext_raw

    return clip_video(
        video_path=str(video_path),
        start=start,
        end=end,
        output_path=output_path,
        codec=codec,
        extra_args=extra_args,
        overwrite=overwrite,
        default_output_dir=default_output_dir,
        scale_width=scale_width,
        quality=quality,
        output_ext=output_ext,
    )


def _parse_arguments(
    argv: Optional[List[str]] = None,
) -> Tuple[argparse.ArgumentParser, argparse.Namespace]:
    parser = argparse.ArgumentParser(
        description="FFmpeg을 이용해 영상의 특정 구간을 자릅니다"
    )
    parser.add_argument("input", nargs="?", help="클립할 원본 영상 경로")
    parser.add_argument("--start", "-s", type=float, help="시작 시간 (초)")
    parser.add_argument("--end", "-e", type=float, help="종료 시간 (초)")
    parser.add_argument(
        "--output", "-o", help="출력 파일 경로 (지정하지 않으면 원본 이름 기반)"
    )
    parser.add_argument(
        "--codec",
        "-c",
        default="copy",
        help="복사 모드 또는 재인코딩 코덱 (기본: copy)",
    )
    parser.add_argument(
        "--reencode", action="store_true", help="copy가 아닌 재인코딩 libx264를 사용"
    )
    parser.add_argument(
        "--scale",
        type=int,
        help="출력 너비(px, 비율 유지)",
    )
    parser.add_argument(
        "--quality",
        type=int,
        choices=list(range(0, 52)),
        metavar="CRF",
        help="x264/crf 화질 값 (0-51, 낮을수록 고품질)",
    )
    parser.add_argument(
        "--ext",
        help="출력 확장자 (예: mp4, gif). 기본은 입력과 동일",
    )
    parser.add_argument(
        "--no-overwrite", action="store_true", help="기존 출력 파일을 덮어쓰지 않음"
    )
    parser.add_argument("--extra", nargs=argparse.REMAINDER, help="FFmpeg 추가 옵션")
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="대화형으로 비디오와 시간, 출력 경로를 입력합니다",
    )
    return parser, parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    parser, args = _parse_arguments(argv)
    codec = "libx264" if args.reencode else args.codec
    extra = args.extra if args.extra else None
    overwrite = not args.no_overwrite

    if args.interactive:
        results = interactive_clip(
            codec=codec,
            extra_args=extra,
            overwrite=overwrite,
            scale_width=args.scale,
            quality=args.quality,
            output_ext=args.ext,
        )
    else:
        if not args.input or args.start is None or args.end is None:
            parser.error(
                "비대화형 모드에서는 입력 파일과 시작/종료 시간이 모두 필요합니다"
            )
        results = clip_video(
            video_path=args.input,
            start=args.start,
            end=args.end,
            output_path=args.output,
            codec=codec,
            extra_args=extra,
            overwrite=overwrite,
            scale_width=args.scale,
            quality=args.quality,
            output_ext=args.ext,
        )

    print(f"✅ 클립 생성 완료: {results.output_path} ({results.duration:.2f}s)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"❌ {exc}")
        raise SystemExit(1)
