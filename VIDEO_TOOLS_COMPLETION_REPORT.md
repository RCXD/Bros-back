# 영상 처리 도구 최종 완성 보고서

## 완성된 기능

### 1. YouTube 영상 부분 다운로드 ✅

**위치:** `apps/test/video/youtube_downloader.py`

**주요 기능:**
- YouTube 영상 다운로드
- 원하는 구간 선택 가능
- **Rate limit 자동 재시도** (5~20회 지정 가능)
- 진행률 표시
- 자동 임시 파일 정리

**사용 방법:**
```bash
# 대화형 모드
python apps/test/video/downloder.py -i

# 명령줄 (기본 5회 재시도)
python apps/test/video/downloder.py "URL" 10 30

# Rate limit 회피 (20회 재시도)
python apps/test/video/downloder.py "URL" 10 30 --retries 20
```

**Python 코드:**
```python
from apps.test.video.youtube_downloader import YouTubeDownloader

downloader = YouTubeDownloader(output_dir="./videos")
file = downloader.download_clip(
    url="https://www.youtube.com/watch?v=...",
    start_time=10,
    duration=30,
    max_retries=15  # Rate limit 회피
)
```

### 2. 영상을 GIF로 변환 ✅

**위치:** `apps/test/video/converter.py`

**주요 기능:**
- 영상의 원하는 구간을 GIF로 변환
- 프레임 속도(FPS) 조절
- 이미지 리사이징
- 품질 조정
- 배치 처리 (여러 구간 한번에)
- 대화형 모드

**사용 방법:**
```bash
# 대화형 모드
python apps/test/video/video_to_gif.py -i video.mp4

# 명령줄
python apps/test/video/video_to_gif.py video.mp4 10 5 --fps 10 --width 640

# 배치 처리
python apps/test/video/video_to_gif.py video.mp4 --batch clips.json
```

**Python 코드:**
```python
from apps.test.video.converter import VideoToGifConverter

converter = VideoToGifConverter(output_dir="./gifs")

# 단일 변환
result = converter.convert_to_gif(
    video_path="video.mp4",
    start_time=10,
    duration=5,
    fps=10,
    width=640
)

# 배치 변환
clips = [
    {"start_time": 0, "duration": 5, "name": "clip1"},
    {"start_time": 10, "duration": 5, "name": "clip2"},
]
results = converter.batch_convert(video_path="video.mp4", clips=clips)
```

### 3. 통합 워크플로우 ✅

**YouTube 다운로드 → GIF 변환 완전 자동화**

```python
from apps.test.video.youtube_downloader import YouTubeDownloader
from apps.test.video.converter import VideoToGifConverter

# 1단계: 다운로드 (Rate limit 자동 재시도)
downloader = YouTubeDownloader(output_dir="./downloads")
video_path = downloader.download_clip(
    url="https://www.youtube.com/watch?v=...",
    start_time=0,
    duration=60,
    max_retries=15
)

# 2단계: GIF 변환
converter = VideoToGifConverter(output_dir="./gifs")
gif_path = converter.convert_to_gif(
    video_path=video_path,
    start_time=10,
    duration=10,
    fps=10,
    width=640
)

print(f"완료! GIF: {gif_path}")
```

## 새로운 기능: Rate Limit 해결 🎯

### 문제
```
ERROR: [youtube] XXXXXX: Video unavailable. 
This content isn't available, try again later. 
The current session has been rate-limited by YouTube for up to an hour.
```

### 해결책

**자동 재시도 로직이 내장되어 있습니다!**

#### 옵션 1: 재시도 횟수 지정 (권장)

```bash
# 20회 재시도 (점진적 대기)
python apps/test/video/downloder.py "URL" 10 30 --retries 20
```

#### 옵션 2: Python에서 설정

```python
downloader = YouTubeDownloader()
file = downloader.download_clip(
    url="https://www.youtube.com/watch?v=...",
    start_time=10,
    duration=30,
    max_retries=20  # ← 이 값을 증가시키세요
)
```

### 재시도 메커니즘

```
1차: 즉시 재시도
2차: 1초 대기 후
3차: 2초 대기 후
4차: 4초 대기 후
5차: 8초 대기 후
...
최대: 60초 대기
```

### 추천 재시도 값

| 상황 | 값 |
|------|-----|
| 일반 다운로드 | 5-10 |
| Rate limit 경고 | 10-15 |
| 반복 실패 | 15-20 |
| 마지막 시도 | 20+ |

## 파일 구조

```
apps/test/video/
├── youtube_downloader.py     # YouTube 다운로더 (재시도 로직 포함)
├── converter.py              # GIF 변환기
├── downloder.py              # CLI 인터페이스 (--retries 옵션)
├── video_to_gif.py           # GIF 변환 CLI
├── create_test_video.py      # 테스트용 영상 생성
└── README.md                 # 상세 설명서

YOUTUBE_RATE_LIMIT_GUIDE.md   # Rate limit 해결 가이드
```

## 필수 라이브러리

```bash
# YouTube 다운로드
pip install yt-dlp

# GIF 변환
pip install imageio imageio-ffmpeg pillow

# 시스템 도구
# FFmpeg 설치 (https://ffmpeg.org/download.html)
```

## 테스트 및 검증

### 통합 테스트

```bash
python apps/test/functional/test_video_gif_conversion.py --all
```

테스트 옵션:
- `--workflow` - 다운로드 + GIF 변환 통합 테스트
- `--conversion` - GIF 변환만 테스트
- `--batch` - 배치 변환 테스트

## 사용 예제

### 예제 1: 단순 다운로드

```bash
python apps/test/video/downloder.py "https://www.youtube.com/watch?v=..." 0 30
```

### 예제 2: Rate Limit 회피

```bash
python apps/test/video/downloder.py "https://www.youtube.com/watch?v=..." 0 30 --retries 20
```

### 예제 3: 다운로드 → GIF 변환

```bash
# 1. 다운로드 (Rate limit 자동 처리)
python apps/test/video/downloder.py "https://www.youtube.com/watch?v=..." 0 60 -o ./videos --retries 15

# 2. GIF 변환 (대화형)
python apps/test/video/video_to_gif.py -i ./videos/clip_0s_60s.mp4
```

### 예제 4: Python 스크립트

```python
from apps.test.video.youtube_downloader import YouTubeDownloader
from apps.test.video.converter import VideoToGifConverter

# 설정
downloader = YouTubeDownloader(output_dir="./my_videos")
converter = VideoToGifConverter(output_dir="./my_gifs")

try:
    # 다운로드 (Rate limit 자동 회피)
    print("다운로드 중...")
    video = downloader.download_clip(
        url="https://www.youtube.com/watch?v=...",
        start_time=10,
        duration=60,
        max_retries=15
    )
    
    # GIF 변환
    print("GIF 변환 중...")
    gif = converter.convert_to_gif(
        video_path=video,
        start_time=20,
        duration=10,
        fps=10,
        width=640
    )
    
    print(f"완료! {gif}")

except Exception as e:
    print(f"에러: {e}")
```

## 주요 개선사항

### youtube_downloader.py 개선사항

✅ **Rate limit 자동 재시도**
- 최대 재시도 횟수 지정 가능
- 지수 백오프 대기 (1초 → 2초 → 4초 → ... → 60초)
- 자동 에러 감지 및 복구

✅ **향상된 오류 처리**
- Rate limit 에러 감지
- 네트워크 타임아웃 설정
- 사용자 에이전트 위장

✅ **사용자 친화적**
- 명확한 진행 메시지
- 재시도 상태 표시
- 최종 성공/실패 보고

### CLI 도구 개선사항

✅ **downloder.py**
- `--retries` 옵션 추가 (기본값: 5)
- Rate limit 관련 문서 포함
- 대화형 모드 유지

✅ **video_to_gif.py**
- 완전한 옵션 지원
- 배치 처리 지원
- 대화형 모드 지원

## 문서

### 📖 메인 가이드
- `apps/test/video/README.md` - 사용법, API, 예제

### 📖 Rate Limit 가이드
- `YOUTUBE_RATE_LIMIT_GUIDE.md` - Rate limit 문제 해결 (이 파일!)

## 주의사항

### ⚠️ YouTube 이용약관 준수
- 개인 학습/테스트 목적으로만 사용
- 저작권이 있는 영상은 동의 필요
- 과도한 다운로드 금지

### ⚠️ Rate Limit 에티켓
- 너무 높은 재시도 설정 금지 (권장: 20 이하)
- 필요한 만큼만 재시도
- 대량 다운로드는 피하기

## 최종 상태

| 항목 | 상태 | 비고 |
|-----|------|------|
| YouTube 다운로드 | ✅ 완성 | Rate limit 자동 처리 |
| GIF 변환 | ✅ 완성 | 모든 옵션 지원 |
| CLI 도구 | ✅ 완성 | 대화형/명령줄 모두 |
| 통합 테스트 | ✅ 완성 | functional 테스트 포함 |
| 문서 | ✅ 완성 | 상세 가이드 제공 |

## 다음 단계 (선택사항)

1. **고급 기능:**
   - 자막 다운로드
   - 음성만 추출 (MP3)
   - 여러 품질 옵션

2. **최적화:**
   - 다중 처리
   - 캐싱 메커니즘
   - 메모리 최적화

3. **UI 개선:**
   - 진행률 바
   - 일괄 처리 대시보드
   - 웹 인터페이스

---

**모든 기능이 준비되었습니다!**
Rate limit 문제도 자동으로 처리되므로 안심하고 사용하세요.
