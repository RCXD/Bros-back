# 영상 처리 도구 모음

YouTube 영상 다운로드, GIF 변환 등을 수행하는 Python 모듈입니다.

## 포함된 도구

1. **youtube_downloader.py** - YouTube 영상 부분 다운로드
2. **converter.py** - 영상을 GIF로 변환
3. **downloder.py** - YouTube 다운로더 CLI/대화형 인터페이스
4. **video_to_gif.py** - GIF 변환 CLI/대화형 인터페이스
5. **create_test_video.py** - 테스트용 샘플 영상 생성

## 설치

### 1. 필수 라이브러리 설치

```bash
# YouTube 다운로더
pip install yt-dlp

# GIF 변환
pip install imageio imageio-ffmpeg pillow
```

### 2. FFmpeg 설치

**Windows:**
```powershell
# Chocolatey 사용 (권장)
choco install ffmpeg

# 또는 https://ffmpeg.org/download.html에서 다운로드 후 PATH에 추가
```

**macOS:**
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install ffmpeg
```

## 사용법

### 1. YouTube 영상 다운로드

#### 대화형 모드 (권장)

```bash
python apps/test/video/downloder.py -i
```

#### 명령줄 인자

```bash
python apps/test/video/downloder.py "<URL>" <시작시간> <길이>

# 예제: 10초부터 30초 길이 다운로드
python apps/test/video/downloder.py "https://www.youtube.com/watch?v=..." 10 30

# Rate limit 회피를 위해 재시도 횟수 증가
python apps/test/video/downloder.py "https://www.youtube.com/watch?v=..." 10 30 --retries 10
```

#### Python 코드

```python
from apps.test.video.youtube_downloader import YouTubeDownloader

downloader = YouTubeDownloader(output_dir="./clips")
file_path = downloader.download_clip(
    url="https://www.youtube.com/watch?v=...",
    start_time=10,
    duration=30,
    max_retries=10  # Rate limit 회피
)
print(f"저장됨: {file_path}")
```

### 2. 영상을 GIF로 변환

#### 대화형 모드 (권장)

```bash
python apps/test/video/video_to_gif.py -i <영상파일>

# 예제
python apps/test/video/video_to_gif.py -i download.mp4
```

인터랙티브하게 다음을 입력합니다:
- 시작 시간 (초)
- GIF 길이 (초)
- 프레임 속도 (FPS)
- 너비 (선택사항)
- 저장 파일명

#### 명령줄 인자

```bash
python apps/test/video/video_to_gif.py <영상파일> <시작> <길이> [옵션]

# 예제
python apps/test/video/video_to_gif.py video.mp4 10 5 --fps 10 --width 640 --output output.gif
```

#### Python 코드

```python
from apps.test.video.converter import VideoToGifConverter

converter = VideoToGifConverter(output_dir="./gifs")

# 단일 변환
result = converter.convert_to_gif(
    video_path="video.mp4",
    start_time=10,      # 10초부터
    duration=5,         # 5초 길이
    fps=10,             # 10 FPS
    width=640           # 너비 640px
)
print(f"생성됨: {result}")
```

#### 배치 변환 (여러 GIF 한번에)

```python
from apps.test.video.converter import VideoToGifConverter

converter = VideoToGifConverter(output_dir="./gifs")

clips = [
    {"start_time": 0, "duration": 3, "name": "intro"},
    {"start_time": 5, "duration": 5, "name": "scene1"},
    {"start_time": 15, "duration": 4, "name": "scene2"},
]

results = converter.batch_convert(
    video_path="video.mp4",
    clips=clips,
    fps=10,
    width=640
)

for gif_path in results:
    print(f"생성됨: {gif_path}")
```

### 3. 통합: 다운로드 → GIF 변환

```python
from apps.test.video.youtube_downloader import YouTubeDownloader
from apps.test.video.converter import VideoToGifConverter

# 1단계: YouTube 다운로드
downloader = YouTubeDownloader(output_dir="./downloads")
video_path = downloader.download_clip(
    url="https://www.youtube.com/watch?v=...",
    start_time=0,
    duration=30
)

# 2단계: GIF로 변환
converter = VideoToGifConverter(output_dir="./gifs")
gif_path = converter.convert_to_gif(
    video_path=video_path,
    start_time=5,
    duration=10,
    fps=10,
    width=640
)

print(f"완료! GIF: {gif_path}")
```

## 전체 통합 테스트

```bash
python apps/test/functional/test_video_gif_conversion.py --all
```

옵션:
- `--workflow` - 다운로드 + GIF 변환 테스트
- `--conversion` - GIF 변환만 테스트
- `--batch` - 배치 변환 테스트
- `--all` - 모든 테스트

## 파일 구조

```
apps/test/video/
├── youtube_downloader.py        # YouTube 다운로더 클래스
├── converter.py                 # GIF 변환 클래스
├── downloder.py                 # YouTube 다운로더 CLI
├── video_to_gif.py              # GIF 변환 CLI
├── create_test_video.py         # 테스트 영상 생성 도구
└── README.md                    # 이 파일

apps/test/functional/
└── test_video_gif_conversion.py # 통합 테스트
```

## 클래스 API

### YouTubeDownloader

#### `download_clip(url, start_time, duration, output_path=None, max_retries=3)`

YouTube 영상의 일부 다운로드

**매개변수:**
- `url` (str): YouTube 영상 URL
- `start_time` (int): 시작 시간 (초)
- `duration` (int): 다운로드할 길이 (초)
- `output_path` (str, optional): 저장 경로
- `max_retries` (int): 재시도 횟수

**반환값:** 저장된 파일 경로

### VideoToGifConverter

#### `convert_to_gif(video_path, output_path=None, start_time=0, duration=5, fps=10, width=None, quality=7, loop=0)`

영상을 GIF로 변환

**매개변수:**
- `video_path` (str): 입력 영상 경로
- `output_path` (str, optional): 저장 경로
- `start_time` (int): 시작 시간 (초)
- `duration` (int): GIF 길이 (초)
- `fps` (int): 프레임 속도 (기본: 10)
- `width` (int, optional): 출력 너비 (높이는 자동 계산)
- `quality` (int): 품질 1-10 (낮을수록 고품질, 기본: 7)
- `loop` (int): 반복 횟수 (0=무한, 기본: 0)

**반환값:** 저장된 GIF 파일 경로

#### `batch_convert(video_path, clips, output_dir=None, fps=10, width=None)`

여러 구간을 각각 GIF로 변환

**매개변수:**
- `video_path` (str): 입력 영상 경로
- `clips` (list): 클립 목록 (각각 start_time, duration, name 포함)
- `output_dir` (str, optional): 저장 디렉토리
- `fps` (int): 프레임 속도
- `width` (int, optional): 출력 너비

**반환값:** 저장된 GIF 파일 경로 목록

#### `interactive_convert(video_path)`

대화형 모드로 GIF 변환

## 옵션 설정

### 품질 (Quality)
- 1-3: 최고 품질 (파일 크기 큼)
- 4-6: 중간 품질
- 7-10: 낮은 품질 (파일 크기 작음, 기본값: 7)

### 프레임 속도 (FPS)
- 5-10: 느린 애니메이션 (파일 작음)
- 10-20: 일반적인 속도
- 20 이상: 부드러운 애니메이션 (파일 큼)

### 너비 (Width)
- 지정하지 않으면 원본 너비 사용
- 지정하면 높이는 자동 계산
- 권장: 480-1280px

## 예제

### 예제 1: 유튜브에서 다운로드 후 GIF 변환

```bash
# 1. 다운로드 (대화형)
python apps/test/video/downloder.py -i

# 2. GIF 변환 (대화형)
python apps/test/video/video_to_gif.py -i download.mp4
```

### 예제 2: 배치 처리

```python
from apps.test.video.youtube_downloader import YouTubeDownloader
from apps.test.video.converter import VideoToGifConverter
import json

# 다운로드
downloader = YouTubeDownloader(output_dir="./videos")
video_path = downloader.download_clip(
    url="https://www.youtube.com/watch?v=...",
    start_time=0,
    duration=60
)

# 여러 GIF 한번에 생성
converter = VideoToGifConverter(output_dir="./gifs")
clips = [
    {"start_time": 0, "duration": 5, "name": "clip1", "fps": 10},
    {"start_time": 10, "duration": 5, "name": "clip2", "fps": 15},
    {"start_time": 20, "duration": 5, "name": "clip3", "fps": 10},
]

results = converter.batch_convert(
    video_path=video_path,
    clips=clips,
    width=640
)

print(f"생성된 GIF: {len(results)}개")
for gif in results:
    print(f"  - {gif}")
```

## 주의사항

### 1. YouTube 이용약관
- 저작권이 있는 영상 다운로드는 법적 문제가 될 수 있습니다
- 개인 학습/테스트 목적으로만 사용하세요

### 2. 파일 크기
- GIF는 용량이 클 수 있습니다
- 낮은 FPS나 낮은 품질 설정으로 파일 크기 감소
- 큰 폭의 리사이징도 파일 크기 감소

### 3. 처리 시간
- FFmpeg이 설치되어 있어야 합니다
- 영상 길이가 길수록 처리 시간이 깁니다
- 너비 조정을 피하면 처리 속도 향상

## 문제 해결

### FFmpeg을 찾을 수 없음
```
ERROR: ffmpeg not found
```
**해결:** FFmpeg 설치 후 PATH에 추가

### imageio 에러
```
ModuleNotFoundError: No module named 'imageio'
```
**해결:** `pip install imageio imageio-ffmpeg` 실행

### 영상 다운로드 실패
**해결:** 
- URL이 올바른지 확인
- 영상이 삭제되었거나 지역 제한 확인
- `yt-dlp --upgrade` 실행

### YouTube Rate Limit 에러

YouTube가 다운로드 요청을 차단하는 경우:
```
ERROR: [youtube] ...: Video unavailable. This content isn't available...
The current session has been rate-limited by YouTube for up to an hour.
```

**해결 방법:**

1. **재시도 횟수 증가** (권장)
   ```bash
   # 기본 5회 재시도에서 10회 이상으로 증가
   python downloder.py "URL" 10 30 --retries 10
   ```

2. **Python 코드에서**
   ```python
   downloader = YouTubeDownloader(output_dir="./clips")
   file_path = downloader.download_clip(
       url="https://www.youtube.com/watch?v=...",
       start_time=10,
       duration=30,
       max_retries=15  # 최대 15회까지 재시도
   )
   ```

3. **시간 경과 대기**
   - YouTube의 rate limit은 일정 시간 후 자동으로 해제됨 (보통 1시간)
   - 차후에 다시 시도하세요

4. **다른 계정 사용**
   - VPN 또는 다른 네트워크에서 시도
   - YouTube 계정 로그인 시도 (더 나은 rate limit)

5. **yt-dlp 업데이트**
   ```bash
   pip install --upgrade yt-dlp
   ```

## 라이선스

개인 학습 및 테스트 목적으로만 사용하세요.
YouTube 이용약관 및 저작권법을 반드시 준수하세요.
