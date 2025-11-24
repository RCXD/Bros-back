"""
대체 YouTube 다운로더 라이브러리들

지원하는 라이브러리:
    1. yt-dlp (현재 사용 중) - 가장 권장
    2. pytube - 간단하고 가벼움
    3. youtube-dl - 가장 오래되고 안정적
    4. pytubefix - pytube의 포크 (유지보수 활발)
    5. pafy - 다양한 기능

설치:
    pip install yt-dlp
    pip install pytube
    pip install youtube-dl
    pip install pytubefix
    pip install pafy
"""

import subprocess
from pathlib import Path
from datetime import datetime
import time
from typing import Optional, Dict, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PytubeDownloader:
    """pytube를 사용한 다운로더"""

    def __init__(self, output_dir: str = "./downloads"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        try:
            import pytube

            self.pytube = pytube
        except ImportError:
            raise ImportError("pytube가 설치되지 않았습니다. 'pip install pytube' 실행")

    def download_clip(self, url: str, start_time: int = 0, duration: int = 30) -> str:
        """
        pytube로 전체 영상 다운로드 후 ffmpeg로 자르기
        (pytube는 부분 다운로드 미지원)
        """
        try:
            print(f"  📥 pytube로 영상 정보 조회 중...")
            yt = self.pytube.YouTube(url)

            print(f"  제목: {yt.title}")
            print(f"  길이: {yt.length}초")

            # 최고 화질의 진행 중인 스트림 선택
            stream = (
                yt.streams.filter(progressive=True, file_extension="mp4")
                .order_by("resolution")
                .desc()
                .first()
            )

            if not stream:
                raise Exception("다운로드 가능한 스트림 없음")

            print(f"  화질: {stream.resolution}")

            # 전체 영상 다운로드
            temp_path = self.output_dir / f"temp_{int(time.time())}.mp4"
            print(f"  📥 다운로드 중... (이것은 시간이 걸릴 수 있습니다)")
            stream.download(output_path=self.output_dir, filename=temp_path.name)

            # ffmpeg로 자르기
            end_time = start_time + duration
            output_filename = (
                f"pytube_clip_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            )
            output_path = self.output_dir / output_filename

            print(f"  ✂️  ffmpeg로 영상 자르는 중... ({start_time}s ~ {end_time}s)")
            cmd = [
                "ffmpeg",
                "-i",
                str(temp_path),
                "-ss",
                str(start_time),
                "-to",
                str(end_time),
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-c:a",
                "aac",
                "-q:v",
                "5",
                "-y",
                str(output_path),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            # 임시 파일 삭제
            temp_path.unlink()

            return str(output_path)

        except Exception as e:
            raise Exception(f"pytube 다운로드 실패: {str(e)}")


class YoutubeDlDownloader:
    """youtube-dl을 사용한 다운로더 (구버전, 업데이트 없음)"""

    def __init__(self, output_dir: str = "./downloads"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        try:
            import youtube_dl

            self.youtube_dl = youtube_dl
        except ImportError:
            raise ImportError(
                "youtube-dl이 설치되지 않았습니다. 'pip install youtube-dl' 실행"
            )

    def download_clip(self, url: str, start_time: int = 0, duration: int = 30) -> str:
        """youtube-dl로 부분 다운로드"""
        try:
            print(f"  📥 youtube-dl로 영상 정보 조회 중...")

            ydl_opts = {
                "format": "best[ext=mp4]",
                "outtmpl": str(self.output_dir / "youtube_dl_%(title)s_%(id)s.%(ext)s"),
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
                "quiet": False,
            }

            with self.youtube_dl.YoutubeDL(ydl_opts) as ydl:
                print(f"  📥 다운로드 중...")
                info = ydl.extract_info(url, download=True)

                # 다운로드된 파일 경로
                video_file = ydl.prepare_filename(info)

                # ffmpeg로 자르기
                end_time = start_time + duration
                output_filename = (
                    f"youtube_dl_clip_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
                )
                output_path = self.output_dir / output_filename

                print(f"  ✂️  ffmpeg로 영상 자르는 중... ({start_time}s ~ {end_time}s)")
                cmd = [
                    "ffmpeg",
                    "-i",
                    video_file,
                    "-ss",
                    str(start_time),
                    "-to",
                    str(end_time),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "fast",
                    "-c:a",
                    "aac",
                    "-q:v",
                    "5",
                    "-y",
                    str(output_path),
                ]

                subprocess.run(cmd, capture_output=True, text=True, check=True)

                return str(output_path)

        except Exception as e:
            raise Exception(f"youtube-dl 다운로드 실패: {str(e)}")


class PytubefixDownloader:
    """pytubefix를 사용한 다운로더 (pytube의 활발한 포크)"""

    def __init__(self, output_dir: str = "./downloads"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        try:
            from pytubefix import YouTube

            self.YouTube = YouTube
        except ImportError:
            raise ImportError(
                "pytubefix가 설치되지 않았습니다. 'pip install pytubefix' 실행"
            )

    def download_clip(self, url: str, start_time: int = 0, duration: int = 30) -> str:
        """
        pytubefix로 전체 영상 다운로드 후 ffmpeg로 자르기
        (pytube 호환이지만 더 잘 유지보수됨)
        """
        try:
            print(f"  📥 pytubefix로 영상 정보 조회 중...")
            yt = self.YouTube(url)

            print(f"  제목: {yt.title}")
            print(f"  길이: {yt.length}초")

            # 최고 화질의 진행 중인 스트림 선택
            stream = (
                yt.streams.filter(progressive=True, file_extension="mp4")
                .order_by("resolution")
                .desc()
                .first()
            )

            if not stream:
                raise Exception("다운로드 가능한 스트림 없음")

            print(f"  화질: {stream.resolution}")

            # 전체 영상 다운로드
            temp_path = self.output_dir / f"temp_{int(time.time())}.mp4"
            print(f"  📥 다운로드 중...")
            stream.download(output_path=self.output_dir, filename=temp_path.name)

            # ffmpeg로 자르기
            end_time = start_time + duration
            output_filename = (
                f"pytubefix_clip_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            )
            output_path = self.output_dir / output_filename

            print(f"  ✂️  ffmpeg로 영상 자르는 중... ({start_time}s ~ {end_time}s)")
            cmd = [
                "ffmpeg",
                "-i",
                str(temp_path),
                "-ss",
                str(start_time),
                "-to",
                str(end_time),
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-c:a",
                "aac",
                "-q:v",
                "5",
                "-y",
                str(output_path),
            ]

            subprocess.run(cmd, capture_output=True, text=True, check=True)

            # 임시 파일 삭제
            temp_path.unlink()

            return str(output_path)

        except Exception as e:
            raise Exception(f"pytubefix 다운로드 실패: {str(e)}")


class PafyDownloader:
    """pafy를 사용한 다운로더 (다양한 기능 제공)"""

    def __init__(self, output_dir: str = "./downloads"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        try:
            import pafy

            self.pafy = pafy
        except ImportError:
            raise ImportError("pafy가 설치되지 않았습니다. 'pip install pafy' 실행")

    def download_clip(self, url: str, start_time: int = 0, duration: int = 30) -> str:
        """pafy로 영상 다운로드"""
        try:
            print(f"  📥 pafy로 영상 정보 조회 중...")
            video = self.pafy.new(url)

            print(f"  제목: {video.title}")
            print(f"  길이: {video.length}초")
            print(f"  조회수: {video.viewcount}")

            # 최고 화질 선택
            best = video.getbest(preftype="mp4")
            print(f"  화질: {best.resolution}")

            # 전체 영상 다운로드
            temp_path = self.output_dir / f"temp_{int(time.time())}.mp4"
            print(f"  📥 다운로드 중...")
            best.download(filepath=self.output_dir, filename=temp_path.name)

            # ffmpeg로 자르기
            end_time = start_time + duration
            output_filename = (
                f"pafy_clip_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            )
            output_path = self.output_dir / output_filename

            print(f"  ✂️  ffmpeg로 영상 자르는 중... ({start_time}s ~ {end_time}s)")
            cmd = [
                "ffmpeg",
                "-i",
                str(temp_path),
                "-ss",
                str(start_time),
                "-to",
                str(end_time),
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-c:a",
                "aac",
                "-q:v",
                "5",
                "-y",
                str(output_path),
            ]

            subprocess.run(cmd, capture_output=True, text=True, check=True)

            # 임시 파일 삭제
            temp_path.unlink()

            return str(output_path)

        except Exception as e:
            raise Exception(f"pafy 다운로드 실패: {str(e)}")


# 다운로더 비교 테이블
DOWNLOADER_COMPARISON = {
    "yt-dlp": {
        "장점": [
            "가장 활발한 유지보수",
            "Rate limit 자동 처리",
            "재시도 로직 내장",
            "부분 다운로드 지원",
            "가장 빠른 성능",
        ],
        "단점": ["다소 복잡한 설정"],
        "설치": "pip install yt-dlp",
        "권장도": "⭐⭐⭐⭐⭐",
    },
    "pytube": {
        "장점": ["간단한 API", "가볍고 빠름", "진행 상황 표시"],
        "단점": [
            "부분 다운로드 미지원",
            "유지보수 느림",
            "YouTube 변경에 자주 깨짐",
        ],
        "설치": "pip install pytube",
        "권장도": "⭐⭐",
    },
    "youtube-dl": {
        "장점": ["오래되고 안정적", "많은 사이트 지원"],
        "단점": [
            "더 이상 유지보수 안 함",
            "YouTube에서 자주 작동 안 함",
            "느린 업데이트",
        ],
        "설치": "pip install youtube-dl",
        "권장도": "⭐",
    },
    "pytubefix": {
        "장점": ["pytube의 활발한 포크", "YouTube 변경 빠르게 대응"],
        "단점": ["pytube와 동일한 부분 다운로드 미지원"],
        "설치": "pip install pytubefix",
        "권장도": "⭐⭐⭐",
    },
    "pafy": {
        "장점": ["다양한 메타데이터", "다양한 형식 지원"],
        "단점": ["유지보수 느림", "YouTube 변경에 취약"],
        "설치": "pip install pafy",
        "권장도": "⭐⭐",
    },
}


def show_comparison():
    """다운로더 비교 출력"""
    print("\n" + "=" * 80)
    print("YouTube 다운로더 라이브러리 비교")
    print("=" * 80)

    for lib_name, info in DOWNLOADER_COMPARISON.items():
        print(f"\n📌 {lib_name} {info['권장도']}")
        print(f"   설치: {info['설치']}")

        print(f"   ✅ 장점:")
        for advantage in info["장점"]:
            print(f"      - {advantage}")

        print(f"   ❌ 단점:")
        for disadvantage in info["단점"]:
            print(f"      - {disadvantage}")

    print("\n" + "=" * 80)
    print("권장사항: yt-dlp 사용 (현재 구현 중)")
    print("=" * 80)


def get_downloader(library: str, output_dir: str = "./downloads"):
    """라이브러리 이름으로 다운로더 인스턴스 생성"""
    library = library.lower()

    downloaders = {
        "pytube": PytubeDownloader,
        "youtube-dl": YoutubeDlDownloader,
        "pytubefix": PytubefixDownloader,
        "pafy": PafyDownloader,
    }

    if library not in downloaders:
        raise ValueError(
            f"지원하지 않는 라이브러리: {library}. 지원: {list(downloaders.keys())}"
        )

    return downloaders[library](output_dir)


if __name__ == "__main__":
    show_comparison()
