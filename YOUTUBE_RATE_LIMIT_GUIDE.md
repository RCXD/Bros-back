# YouTube Rate Limit 해결 가이드

## 문제 상황

YouTube에서 다운로드 요청을 차단할 때 나타나는 에러:

```
ERROR: [youtube] XXXXXX: Video unavailable. This content isn't available, try again later. 
The current session has been rate-limited by YouTube for up to an hour. 
It is recommended to use `-t sleep` to add a delay between video requests...
```

## 원인

- YouTube의 보안 정책으로 인한 일시적 차단
- 짧은 시간에 너무 많은 요청
- 봇으로 의심되는 활동 패턴

## 해결 방법

### 방법 1: 재시도 옵션 사용 (권장) ⭐

**명령줄:**
```bash
# 기본 5회에서 10회 이상 재시도
python apps/test/video/downloder.py "URL" <시작> <길이> --retries 10

# 더 많은 재시도 (최대 20회까지 가능)
python apps/test/video/downloder.py "URL" <시작> <길이> --retries 20
```

**Python 코드:**
```python
from apps.test.video.youtube_downloader import YouTubeDownloader

downloader = YouTubeDownloader(output_dir="./videos")

# 최대 15회까지 재시도
file_path = downloader.download_clip(
    url="https://www.youtube.com/watch?v=...",
    start_time=0,
    duration=30,
    max_retries=15  # <-- 이 값을 증가시키세요
)

print(f"다운로드 완료: {file_path}")
```

**동작 원리:**
- 각 실패 후 지수 백오프(exponential backoff) 대기
- 1차 실패: 1초 대기 후 재시도
- 2차 실패: 2초 대기 후 재시도
- 3차 실패: 4초 대기 후 재시도
- 4차 실패: 8초 대기 후 재시도
- 5차 이상: 최대 60초까지 대기

### 방법 2: 시간 경과 후 재시도

Rate limit은 일정 시간 후 자동 해제됩니다:

```bash
# 1시간 대기 후 다시 시도
python apps/test/video/downloder.py "URL" <시작> <길이>
```

### 방법 3: 다른 네트워크에서 시도

- **VPN 사용:**
  - 다른 지역의 VPN 연결
  - 다시 다운로드 시도

- **다른 와이파이 사용:**
  - 회사 네트워크 또는 모바일 핫스팟
  - 공용 와이파이

### 방법 4: yt-dlp 업데이트

최신 버전에는 더 나은 YouTube 대응이 포함되어 있습니다:

```bash
pip install --upgrade yt-dlp
```

### 방법 5: 계정 인증

YouTube 계정으로 로그인하면 더 나은 rate limit을 받을 수 있습니다:

```bash
# 계정 쿠키 인증 사용 (고급)
python apps/test/video/downloder.py "URL" <시작> <길이> --retries 10
```

## 실전 예제

### 예제 1: 재시도로 해결 (가장 효과적)

```bash
# 터미널에서
cd c:\Users\M\Bros-back-clone2

# 20회 재시도로 시도
python apps/test/video/downloder.py "https://www.youtube.com/watch?v=..." 0 30 --retries 20
```

**예상 출력:**
```
📥 YouTube 영상 다운로드 중...
   URL: https://www.youtube.com/watch?v=...

📥 다운로드 시도 1/20...
   진행률: ...

⚠️ Rate limit 감지. 재시도 대기 중...

⏳ 1초 대기 중... (시도 2/20)
📥 다운로드 시도 2/20...
   진행률: ...

⏳ 2초 대기 중... (시도 3/20)
📥 다운로드 시도 3/20...
   ...

✅ 완료!
   저장 위치: /path/to/video.mp4
```

### 예제 2: Python에서 큰 재시도 횟수 설정

```python
from apps.test.video.youtube_downloader import YouTubeDownloader

downloader = YouTubeDownloader(output_dir="./my_videos")

try:
    print("영상 다운로드 중... (최대 20회 재시도)")
    file_path = downloader.download_clip(
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        start_time=0,
        duration=60,
        max_retries=20  # ← 많은 재시도
    )
    
    print(f"성공! {file_path}")
    
except Exception as e:
    print(f"실패: {e}")
    print("다른 방법을 시도하세요:")
    print("1. 1시간 대기 후 재시도")
    print("2. VPN으로 다른 위치에서 시도")
    print("3. 다른 계정으로 시도")
```

## 재시도 횟수 가이드

| 상황 | 권장 재시도 | 설명 |
|-----|-----------|------|
| 처음 시도 | 5회 (기본값) | 일반적인 요청 |
| Rate limit 경고 | 10회 | 약간의 제한 상태 |
| 반복되는 실패 | 15회 | 심각한 제한 상태 |
| 여러 번 실패 후 | 20회 | 최대 노력 |

## 작동 원리

### 재시도 로직 흐름

```
1차 시도
    ├─ 성공 → 완료
    └─ 실패 (Rate limit)
    
2차 시도 (1초 대기 후)
    ├─ 성공 → 완료
    └─ 실패 (Rate limit)
    
3차 시도 (2초 대기 후)
    ├─ 성공 → 완료
    └─ 실패 (Rate limit)
    
4차 시도 (4초 대기 후)
    ├─ 성공 → 완료
    └─ 실패 (Rate limit)

...

N차 시도 (최대 60초 대기)
    ├─ 성공 → 완료
    └─ 실패 → 최종 실패 반환
```

### 기술 세부사항

- **지수 백오프:** 각 실패 후 대기 시간이 2배씩 증가 (최대 60초)
- **타임아웃:** HTTP 요청 타임아웃 30초로 설정
- **사용자 에이전트:** 일반 브라우저로 위장

## 문제 해결

### Q1: 재시도를 해도 여전히 안 됩니다

**A:** 다음을 시도하세요:
1. 1시간 대기 후 재시도
2. VPN 사용하여 다른 지역에서 시도
3. 다른 계정으로 시도
4. 다른 영상으로 테스트 (영상 자체의 문제일 수 있음)

### Q2: 재시도 횟수는 몇 개가 좋습니까?

**A:** 일반적으로:
- 기본: 5-10회
- 심각한 제한: 15-20회
- 절대 최대: 30회 (하지만 효과는 떨어질 가능성)

### Q3: 재시도 시간을 줄일 수 있습니까?

**A:** 아니요. 지수 백오프는 YouTube의 대역폭 보호입니다. 조정하면 더 높은 차단 가능성이 있습니다.

### Q4: VPN을 사용해야 합니까?

**A:** Rate limit 해제 후 재시도가 일반적입니다. VPN은 다음과 같은 경우 도움이 됩니다:
- 재시도 후에도 계속 실패
- 특정 지역의 제한 (드문 경우)

## 법적 주의

YouTube 이용약관을 준수하세요:
- 개인 학습/테스트 목적으로만 사용
- 저작권이 있는 영상은 원본자의 동의 필요
- 과도한 다운로드는 위약 위반

## 추가 정보

- [yt-dlp GitHub](https://github.com/yt-dlp/yt-dlp)
- [YouTube Terms of Service](https://www.youtube.com/static?template=terms)
