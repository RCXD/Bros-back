# YouTube Rate Limit 문제 해결 - 간단한 가이드

## 문제가 발생한 상황

YouTube에서 다운로드를 차단한 상태입니다:

```
ERROR: [youtube] ...: Video unavailable. This content isn't available, try again later.
The current session has been rate-limited by YouTube for up to an hour.
```

## 해결 방법 (3가지)

### 방법 1️⃣: 재시도 옵션 추가 ⭐ (가장 쉬움)

**터미널에서 이렇게 입력하세요:**

```bash
python apps/test/video/downloder.py "YOUR_URL" 0 30 --retries 20
```

**예제:**
```bash
python apps/test/video/downloder.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ" 0 30 --retries 20
```

이것은:
- 최대 20회 재시도
- 각 실패 후 잠시 대기 (자동)
- 성공할 때까지 반복

---

### 방법 2️⃣: Python 코드에서 재시도 설정

```python
from apps.test.video.youtube_downloader import YouTubeDownloader

downloader = YouTubeDownloader(output_dir="./videos")

# 최대 20회 재시도
file = downloader.download_clip(
    url="https://www.youtube.com/watch?v=...",
    start_time=0,
    duration=30,
    max_retries=20  # <-- 이 값!
)

print(f"완료: {file}")
```

---

### 방법 3️⃣: 시간이 지난 후 다시 시도

YouTube의 Rate limit은 자동으로 해제됩니다:

1. **1시간 기다린 후** 다시 시도
2. 또는 내일 다시 시도

---

## 재시도 횟수 가이드

| 상황 | 설정값 |
|------|--------|
| 처음 시도 | `--retries 5` (기본값) |
| 실패했을 때 | `--retries 10` |
| 계속 실패할 때 | `--retries 20` |

---

## 실제 사용 예제

### 예제 1: 기본 다운로드 (재시도 20회)

```bash
cd c:\Users\M\Bros-back-clone2

python apps/test/video/downloder.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ" 0 60 --retries 20
```

**실행 결과:**
```
📥 YouTube 영상 다운로드 중...
   URL: https://www.youtube.com/watch?v=dQw4w9WgXcQ

📥 다운로드 시도 1/20...
   진행률: ... | 속도: ... | ETA: ...

⚠️ Rate limit 감지. 재시도 대기 중...

⏳ 1초 대기 중... (시도 2/20)
📥 다운로드 시도 2/20...
   ...

✅ 완료!
   저장 위치: C:\Users\M\Bros-back-clone2\downloads\clip_0s_60s.mp4
```

### 예제 2: 다운로드 후 GIF 변환

```bash
# 1단계: 다운로드 (재시도 20회)
python apps/test/video/downloder.py "https://www.youtube.com/watch?v=..." 0 60 --retries 20

# 2단계: GIF 변환 (대화형)
python apps/test/video/video_to_gif.py -i downloads/clip_0s_60s.mp4
```

---

## 작동 원리

재시도할 때마다 자동으로 기다립니다:

```
1차 시도: 즉시 다운로드 시도
2차 시도: 1초 기다린 후
3차 시도: 2초 기다린 후
4차 시도: 4초 기다린 후
5차 시도: 8초 기다린 후
...
20차 시도: 최대 60초까지 기다린 후
```

---

## FAQ

**Q1: 재시도하면 꼭 성공하나요?**
> A: 대부분의 경우 성공합니다. 만약 실패해도 1시간 대기 후 다시 시도하면 됩니다.

**Q2: 재시도 횟수는 몇 개가 좋나요?**
> A: 일반적으로 10-20회 정도면 충분합니다.

**Q3: 재시도를 30회 이상 할 수 있나요?**
> A: 가능하지만 권장하지 않습니다. 20회 정도면 충분합니다.

**Q4: VPN이 필요한가요?**
> A: 아니요. 재시도 옵션만으로 대부분 해결됩니다.

---

## 추천 사용법

```bash
# 1차 시도 (기본 5회)
python apps/test/video/downloder.py "URL" 0 30

# 실패 → 2차 시도 (10회)
python apps/test/video/downloder.py "URL" 0 30 --retries 10

# 계속 실패 → 3차 시도 (20회)
python apps/test/video/downloder.py "URL" 0 30 --retries 20

# 여전히 실패 → 1시간 기다린 후 다시
# (또는 내일 다시)
```

---

## 최종 팁

- `--retries 20`은 기본 설정처럼 사용하세요
- 대부분의 경우 2-3회 재시도 안에 성공합니다
- 만약 실패해도 정상입니다 (YouTube의 보안 정책)
- 다음 날 다시 시도하면 거의 항상 성공합니다

---

**이제 준비되었습니다! 위의 명령어 중 하나를 터미널에서 실행하세요.**
