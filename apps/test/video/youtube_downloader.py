"""
YouTube 영상 부분 다운로드 모듈

사용법:
    downloader = YouTubeDownloader()
    downloader.download_clip(
        url="https://www.youtube.com/watch?v=...",
        start_time=10,      # 시작 시간 (초)
        duration=30,        # 다운로드할 영상 길이 (초)
        output_path="./downloads"
    )
"""

import os
import subprocess
import time
from pathlib import Path
from typing import Optional
import yt_dlp


class YouTubeDownloader:
    """YouTube 영상 부분 다운로드 클래스"""

    def __init__(self, output_dir: str = "./downloads"):
        """
        초기화

        Args:
            output_dir: 다운로드 파일 저장 디렉토리
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def download_clip(
        self,
        url: str,
        start_time: int,
        duration: int,
        output_path: Optional[str] = None,
        video_format: str = "best[height<=360]/best",
        max_retries: int = 5,
    ) -> str:
        """
        YouTube 영상의 일부분을 다운로드 (또는 전체 영상)

        참고: FFmpeg이 설치되어 있으면 부분 다운로드가 자동으로 수행됩니다.
              FFmpeg이 없으면 전체 영상을 다운로드합니다.

        Args:
            url: YouTube 영상 URL
            start_time: 시작 시간 (초)
            duration: 다운로드할 영상 길이 (초)
            output_path: 저장 경로 (지정하지 않으면 output_dir 사용)
            video_format: 비디오 포맷 (기본값: best[height<=360]/best - 저용량)
            max_retries: 최대 재시도 횟수 (기본값: 5)

        Returns:
            다운로드된 파일 경로

        Raises:
            ValueError: 잘못된 입력값
            Exception: 다운로드 실패
        """
        # 입력값 검증
        if not url:
            raise ValueError("YouTube URL을 입력해주세요")
        if start_time < 0:
            raise ValueError("시작 시간은 0 이상이어야 합니다")
        if duration <= 0:
            raise ValueError("다운로드 길이는 0보다 커야 합니다")

        # 출력 경로 설정
        if output_path is None:
            output_path = self.output_dir
        else:
            output_path = Path(output_path)
            output_path.mkdir(parents=True, exist_ok=True)

        try:
            print(f"📥 YouTube 영상 다운로드 중...")
            print(f"   URL: {url}")
            print(f"   시작: {start_time}초, 길이: {duration}초")

            # FFmpeg 설치 여부 확인
            has_ffmpeg = self._check_ffmpeg_installed()

            if has_ffmpeg:
                print(f"   FFmpeg: 설치됨 (부분 다운로드 가능)")
                # FFmpeg을 사용한 부분 다운로드
                return self._download_with_ffmpeg(
                    url, output_path, start_time, duration, video_format, max_retries
                )
            else:
                print(f"   FFmpeg: 미설치 (전체 영상만 다운로드 가능)")
                print(f"   💡 부분 다운로드를 원하면 FFmpeg을 설치하세요:")
                print(f"      https://ffmpeg.org/download.html")

                # FFmpeg 없이 전체 영상 다운로드
                return self._download_without_ffmpeg(
                    url, output_path, video_format, max_retries
                )

            print(f"\n✅ 완료!")
            print(f"   저장 위치: {output_file.absolute()}")
            print(f"   파일 크기: {self._get_file_size(output_file)}")

            return str(output_file)

        except Exception as e:
            # 에러 발생 시 임시 파일 정리
            raise Exception(f"영상 다운로드 실패: {str(e)}")

    def _check_ffmpeg_installed(self) -> bool:
        """FFmpeg 설치 여부 확인"""
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"], capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def _download_with_ffmpeg(
        self,
        url: str,
        output_path: Path,
        start_time: int,
        duration: int,
        video_format: str,
        max_retries: int,
    ) -> str:
        """FFmpeg을 사용하여 부분 다운로드"""
        # 임시 파일 경로 (전체 영상)
        temp_file = output_path / "temp_full_video.mp4"

        # 최종 파일 경로 (일부분)
        output_file = output_path / f"clip_{start_time}s_{duration}s.mp4"

        try:
            # Step 1: 전체 영상 다운로드 (재시도 로직 포함)
            self._download_full_video_with_retry(
                url, str(temp_file), video_format, max_retries
            )

            # Step 2: 영상 일부분 자르기
            print(f"\n✂️  영상 자르는 중...")
            print(f"   시작: {start_time}초, 길이: {duration}초")

            self._cut_video(str(temp_file), str(output_file), start_time, duration)

            # Step 3: 임시 파일 삭제
            if temp_file.exists():
                temp_file.unlink()
                print(f"   ✓ 임시 파일 삭제됨")

            print(f"\n✅ 다운로드 완료!")
            print(f"   파일: {output_file}")
            print(f"   크기: {output_file.stat().st_size:,} bytes")

            return str(output_file)

        except Exception as e:
            # 에러 발생 시 임시 파일 정리
            if temp_file.exists():
                temp_file.unlink()
            raise Exception(f"영상 다운로드 실패: {str(e)}")

    def _download_without_ffmpeg(
        self,
        url: str,
        output_path: Path,
        video_format: str,
        max_retries: int,
    ) -> str:
        """FFmpeg 없이 전체 영상 다운로드"""
        try:
            # 최종 파일 경로 (전체 영상)
            output_template = str(output_path / "video_%(title)s_%(id)s.%(ext)s")

            # Step 1: 전체 영상 다운로드 (재시도 로직 포함)
            self._download_full_video_with_retry(
                url, output_template, video_format, max_retries
            )

            # 다운로드된 파일 찾기
            files = list(output_path.glob("video_*.mp4"))
            if not files:
                files = list(output_path.glob("video_*.*"))

            if files:
                output_file = files[-1]  # 가장 최근 파일
                print(f"\n✅ 다운로드 완료!")
                print(f"   파일: {output_file}")
                print(f"   크기: {output_file.stat().st_size:,} bytes")
                return str(output_file)
            else:
                raise Exception("다운로드된 파일을 찾을 수 없습니다")

        except Exception as e:
            raise Exception(f"영상 다운로드 실패: {str(e)}")

    def _download_full_video(
        self, url: str, output_path: str, video_format: str
    ) -> None:
        """
        YouTube에서 전체 영상 다운로드 (yt-dlp 사용)

        Args:
            url: YouTube URL
            output_path: 저장 경로
            video_format: 비디오 포맷
        """
        ydl_opts = {
            "format": video_format,
            "outtmpl": output_path,
            "quiet": False,
            "no_warnings": False,
            "progress_hooks": [self._progress_hook],
            # Rate limit 대응 옵션
            "socket_timeout": 30,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

    def _download_full_video_with_retry(
        self,
        url: str,
        output_path: str,
        video_format: str,
        max_retries: int = 5,
    ) -> None:
        """
        재시도 로직을 포함하여 YouTube 영상 다운로드

        Args:
            url: YouTube URL
            output_path: 저장 경로
            video_format: 비디오 포맷
            max_retries: 최대 재시도 횟수
        """
        last_error = None
        retry_count = max_retries

        for attempt in range(1, retry_count + 1):
            try:
                if attempt > 1:
                    # 재시도 전 대기 (지수 백오프)
                    wait_time = min(2 ** (attempt - 2), 60)
                    print(
                        f"\n⏳ {wait_time}초 대기 중... (시도 {attempt}/{retry_count})"
                    )
                    time.sleep(wait_time)

                print(f"\n📥 다운로드 시도 {attempt}/{retry_count}...")
                self._download_full_video(url, output_path, video_format)
                return  # 성공하면 함수 종료

            except Exception as e:
                last_error = e
                error_msg = str(e)

                # Rate limit 에러인지 확인
                if (
                    "rate-limited" in error_msg.lower()
                    or "unavailable" in error_msg.lower()
                    or "429" in error_msg
                ):
                    if attempt < retry_count:
                        print(f"⚠️  Rate limit 감지. 재시도 대기 중...")
                        continue
                    else:
                        print(f"❌ Rate limit으로 인해 다운로드 실패")
                else:
                    # 다른 에러는 바로 실패
                    raise

        # 모든 재시도 실패
        raise Exception(
            f"최대 {retry_count}회 재시도 후에도 다운로드 실패: {last_error}"
        )

    def _cut_video(
        self, input_file: str, output_file: str, start_time: int, duration: int
    ) -> None:
        """
        ffmpeg을 사용하여 영상 일부분 자르기

        Args:
            input_file: 입력 파일 경로
            output_file: 출력 파일 경로
            start_time: 시작 시간 (초)
            duration: 영상 길이 (초)
        """
        # ffmpeg 명령어 구성
        cmd = [
            "ffmpeg",
            "-i",
            input_file,
            "-ss",
            str(start_time),  # 시작 시간
            "-t",
            str(duration),  # 길이
            "-c:v",
            "libx264",  # 비디오 코덱
            "-c:a",
            "aac",  # 오디오 코덱
            "-y",  # 기존 파일 덮어쓰기
            output_file,
        ]

        # ffmpeg 실행
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise Exception(f"ffmpeg 실행 실패: {result.stderr}")

    def _progress_hook(self, d):
        """다운로드 진행 상황 출력"""
        if d["status"] == "downloading":
            percent = d.get("_percent_str", "N/A")
            speed = d.get("_speed_str", "N/A")
            eta = d.get("_eta_str", "N/A")
            print(f"\r   진행률: {percent} | 속도: {speed} | ETA: {eta}", end="")
        elif d["status"] == "finished":
            print(f"\r   다운로드 완료!                                    ")

    @staticmethod
    def _get_file_size(file_path: Path) -> str:
        """파일 크기를 읽기 좋은 형식으로 반환"""
        size_bytes = file_path.stat().st_size
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"


def download_youtube_clip(
    url: str,
    start_time: int,
    duration: int,
    output_dir: str = "./downloads",
    max_retries: int = 5,
) -> str:
    """
    간단한 함수 인터페이스

    Args:
        url: YouTube URL
        start_time: 시작 시간 (초)
        duration: 다운로드할 영상 길이 (초)
        output_dir: 저장 디렉토리
        max_retries: 최대 재시도 횟수

    Returns:
        다운로드된 파일 경로
    """
    downloader = YouTubeDownloader(output_dir)
    return downloader.download_clip(url, start_time, duration, max_retries=max_retries)


if __name__ == "__main__":
    import sys

    # 사용 예제
    print("=" * 60)
    print("YouTube 영상 부분 다운로드 도구")
    print("=" * 60)

    # 명령줄 인자 처리
    if len(sys.argv) >= 4:
        url = sys.argv[1]
        start_time = int(sys.argv[2])
        duration = int(sys.argv[3])
        output_dir = sys.argv[4] if len(sys.argv) > 4 else "./downloads"

        try:
            result = download_youtube_clip(url, start_time, duration, output_dir)
            print(f"\n결과: {result}")
        except Exception as e:
            print(f"\n❌ 에러: {str(e)}")
            sys.exit(1)
    else:
        print("\n사용법:")
        print("  python youtube_downloader.py <URL> <시작시간> <길이> [저장경로]")
        print("\n예제:")
        print(
            "  python youtube_downloader.py https://www.youtube.com/watch?v=... 10 30"
        )
        print(
            "  python youtube_downloader.py https://www.youtube.com/watch?v=... 10 30 ./my_clips"
        )
        print("\n매개변수:")
        print("  URL: YouTube 영상 링크")
        print("  시작시간: 영상에서 시작할 시간 (초 단위)")
        print("  길이: 다운로드할 영상 길이 (초 단위)")
        print("  저장경로: 파일을 저장할 디렉토리 (선택사항, 기본값: ./downloads)")
