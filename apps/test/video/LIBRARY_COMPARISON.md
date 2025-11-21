# YouTube 다운로더 라이브러리 비교 & 사용 예제

## 📊 라이브러리 비교 요약

| 라이브러리 | 활발도 | 부분다운로드 | Rate Limit | 성능 | 권장도 |
|-----------|------|----------|-----------|------|------|
| **yt-dlp** | ⭐⭐⭐⭐⭐ | ✅ | ✅ 자동 | 빠움 | ⭐⭐⭐⭐⭐ |
| **pytubefix** | ⭐⭐⭐ | ❌ | ❌ | 보통 | ⭐⭐⭐ |
| **pytube** | ⭐⭐ | ❌ | ❌ | 빠름 | ⭐⭐ |
| **pafy** | ⭐⭐ | ❌ | ❌ | 보통 | ⭐⭐ |
| **youtube-dl** | ⭐ | ❌ | ❌ | 느림 | ⭐ |

---

## 🔧 각 라이브러리별 사용 예제

### 1. **yt-dlp** (✅ 권장 - 현재 사용)

**특징:**
- YouTube의 변경에 빠르게 대응
- Rate limit 자동 처리
- 재시도 로직 내장
- 부분 다운로드 네이티브 지원

**설치:**
```bash
pip install yt-dlp
```

**기본 사용:**
```python
from apps.test.video.youtube_downloader import YouTubeDownloader

downloader = YouTubeDownloader(output_dir="./downloads")

# 부분 다운로드 (효율적)
file_path = downloader.download_clip(
    url="https://www.youtube.com/watch?v=...",
    start_time=10,
    duration=30,
    max_retries=10
)
```

**장점:**
- ✅ 가장 활발한 유지보수
- ✅ YouTube 오류 빠르게 대응
- ✅ 부분 다운로드 지원 (전체 다운로드 불필요)
- ✅ Rate limit 자동 처리
- ✅ 빠른 다운로드 속도

**단점:**
- ❌ 다소 복잡한 설정

**추천 사용 케이스:**
- 프로덕션 환경
- 신뢰성이 중요한 경우
- Rate limit이 문제가 되는 경우

---

### 2. **pytube** (간단함을 원할 때)

**특징:**
- 매우 간단한 API
- 가볍고 빠른 성능
- 진행 상황 표시 지원

**설치:**
```bash
pip install pytube
```

**기본 사용:**
```python
from apps.test.video.alternative_downloaders import PytubeDownloader

downloader = PytubeDownloader(output_dir="./downloads")

# 전체 다운로드 후 ffmpeg로 자르기
file_path = downloader.download_clip(
    url="https://www.youtube.com/watch?v=...",
    start_time=10,
    duration=30
)
```

**장점:**
- ✅ 매우 간단한 API
- ✅ 가볍고 빠름
- ✅ 진행 상황 표시

**단점:**
- ❌ 부분 다운로드 미지원 (전체 다운로드 필요)
- ❌ YouTube 변경에 자주 깨짐
- ❌ 유지보수가 느림
- ⚠️ 큰 파일의 경우 시간 낭비

**추천 사용 케이스:**
- 작은 프로젝트
- 간단함이 중요한 경우
- 교육용 목적

---

### 3. **pytubefix** (pytube 개선 버전)

**특징:**
- pytube의 활발한 포크
- YouTube 변경에 빠른 대응
- pytube와 호환되는 API

**설치:**
```bash
pip install pytubefix
```

**기본 사용:**
```python
from apps.test.video.alternative_downloaders import PytubefixDownloader

downloader = PytubefixDownloader(output_dir="./downloads")

file_path = downloader.download_clip(
    url="https://www.youtube.com/watch?v=...",
    start_time=10,
    duration=30
)
```

**장점:**
- ✅ pytube보다 활발한 유지보수
- ✅ YouTube 변경에 빠른 대응
- ✅ pytube 호환 API

**단점:**
- ❌ 부분 다운로드 미지원
- ❌ 여전히 전체 다운로드 필요

**추천 사용 케이스:**
- pytube를 원하지만 더 나은 유지보수를 원할 때
- 중소 프로젝트

---

### 4. **pafy** (메타데이터가 필요할 때)

**특징:**
- 다양한 메타데이터 제공
- 여러 포맷 지원
- 간단한 API

**설치:**
```bash
pip install pafy
```

**기본 사용:**
```python
from apps.test.video.alternative_downloaders import PafyDownloader

downloader = PafyDownloader(output_dir="./downloads")

file_path = downloader.download_clip(
    url="https://www.youtube.com/watch?v=...",
    start_time=10,
    duration=30
)
```

**pafy로 메타데이터 조회:**
```python
import pafy

video = pafy.new("https://www.youtube.com/watch?v=...")

print(f"제목: {video.title}")
print(f"길이: {video.length}초")
print(f"조회수: {video.viewcount}")
print(f"채널: {video.author}")
print(f"설명: {video.description}")

# 다양한 화질 확인
for stream in video.allstreams:
    print(f"{stream.quality} - {stream.extension}")
```

**장점:**
- ✅ 풍부한 메타데이터
- ✅ 다양한 포맷 지원
- ✅ 간단한 API

**단점:**
- ❌ 유지보수가 느림
- ❌ YouTube 변경에 취약

**추천 사용 케이스:**
- 메타데이터가 중요한 경우
- 다양한 포맷이 필요한 경우

---

### 5. **youtube-dl** (더 이상 권장하지 않음)

**특징:**
- 매우 오래된 라이브러리
- 1000개 이상의 사이트 지원
- 활발한 유지보수 없음

**설치:**
```bash
pip install youtube-dl
```

**기본 사용:**
```python
from apps.test.video.alternative_downloaders import YoutubeDlDownloader

downloader = YoutubeDlDownloader(output_dir="./downloads")

file_path = downloader.download_clip(
    url="https://www.youtube.com/watch?v=...",
    start_time=10,
    duration=30
)
```

**장점:**
- ✅ 매우 오래되고 "안정적"
- ✅ 많은 사이트 지원

**단점:**
- ❌ 더 이상 유지보수하지 않음
- ❌ YouTube에서 자주 작동하지 않음
- ❌ 매우 느린 업데이트

**추천 사용 케이스:**
- ❌ 현재 프로젝트에는 권장하지 않음
- ⚠️ 구형 시스템에서만 고려

---

## 🧪 라이브러리 비교 테스트

### 비교표 출력
```bash
python apps/test/video/compare_downloaders.py --show-comparison
```

### 특정 라이브러리 테스트
```bash
# yt-dlp로 테스트
python apps/test/video/compare_downloaders.py --library yt-dlp <URL> 10 30

# pytube로 테스트
python apps/test/video/compare_downloaders.py --library pytube <URL> 10 30

# pytubefix로 테스트
python apps/test/video/compare_downloaders.py --library pytubefix <URL> 10 30
```

### 모든 라이브러리 비교 테스트
```bash
python apps/test/video/compare_downloaders.py --test <URL> 10 30
```

---

## 📈 성능 비교

### 다운로드 시간 (예상)

| 라이브러리 | 부분 다운로드 | 전체 다운로드 |
|-----------|------------|-----------|
| **yt-dlp** | 2-5초 | 30-60초 |
| **pytube** | N/A | 30-60초 |
| **pytubefix** | N/A | 30-60초 |
| **pafy** | N/A | 30-60초 |
| **youtube-dl** | N/A | 60-120초 |

**주의:** 실제 시간은 네트워크 속도, 파일 크기, YouTube 서버 상태에 따라 달라집니다.

---

## 🎯 선택 가이드

### "빠르고 안정적이어야 한다"
→ **yt-dlp** ⭐⭐⭐⭐⭐ 사용

### "최대한 간단하게 구현하고 싶다"
→ **pytube** 또는 **pytubefix** 사용

### "메타데이터가 중요하다"
→ **pafy** 사용

### "여러 사이트를 지원해야 한다"
→ **youtube-dl** (비권장, yt-dlp 사용 권장)

---

## 🔗 공식 저장소

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - 가장 활발
- [pytube](https://github.com/nficano/pytube)
- [pytubefix](https://github.com/JuanBindez/pytubefix) - pytube 포크
- [pafy](https://github.com/mps-youtube/pafy)
- [youtube-dl](https://github.com/ytdl-org/youtube-dl) - 더 이상 유지보수 안 함

---

## 💡 팁

1. **Rate Limit 문제**
   - yt-dlp 사용 (자동 처리)
   - 또는 재시도 로직 구현

2. **대역폭 절약**
   - yt-dlp의 부분 다운로드 사용
   - 다른 라이브러리는 전체 다운로드 후 ffmpeg 자르기

3. **안정성**
   - yt-dlp 사용 (가장 활발한 유지보수)

4. **간단함**
   - pytube 또는 pytubefix 사용

---

## 📝 다음 단계

현재 구현:
- ✅ yt-dlp (권장)
- ✅ pytube
- ✅ pytubefix
- ✅ pafy
- ✅ youtube-dl

추가 고려사항:
- API 통합 (Flask 앱에 엔드포인트 추가)
- 큐 시스템 (여러 영상 동시 다운로드)
- 캐싱 (이미 다운로드한 영상 재사용)
- 메타데이터 저장소 (다운로드한 영상 정보 저장)
