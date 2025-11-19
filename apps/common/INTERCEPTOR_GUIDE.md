# HTTP Interceptor 테스트 가이드

## 개요
모든 엔드포인트에 자동으로 적용되는 HTTP 인터셉터가 추가되었습니다.
4xx, 5xx 에러 응답 시 자동으로 상세 정보를 로깅합니다.

## 주요 기능

### 1. 자동 에러 로깅
- **4xx 에러**: WARNING 레벨로 로깅 (클라이언트 에러)
- **5xx 에러**: ERROR 레벨로 로깅 (서버 에러)

### 2. 로그 정보
다음 정보가 자동으로 로깅됩니다:
- 타임스탬프
- HTTP 메서드 (GET, POST, PUT, DELETE 등)
- 요청 URL 및 경로
- 클라이언트 IP
- HTTP 상태 코드
- 요청 헤더 (Authorization 토큰은 마스킹)
- 요청 바디 (password, token 등 민감 정보 마스킹)
- 응답 바디

### 3. 로그 파일 위치
- **경로**: `logs/error.log`
- **최대 크기**: 10MB
- **백업 파일**: 최대 10개 유지
- **자동 로테이션**: 파일 크기 초과 시 자동 백업

## 테스트 방법

### 1. 404 에러 테스트
존재하지 않는 엔드포인트에 요청:
```bash
curl http://localhost:8002/nonexistent
```

예상 응답:
```json
{
  "message": "요청하신 리소스를 찾을 수 없습니다",
  "path": "/nonexistent"
}
```

### 2. 401 인증 에러 테스트
토큰 없이 보호된 엔드포인트 요청:
```bash
curl http://localhost:8002/auth/me
```

### 3. 400 잘못된 요청 테스트
필수 파라미터 누락:
```bash
curl -X POST http://localhost:8002/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "test"}'
```

### 4. 로그 확인
```bash
# 실시간 로그 모니터링
tail -f logs/error.log

# 최근 20개 에러 확인
tail -n 20 logs/error.log

# 특정 상태 코드 검색
grep "status_code.*404" logs/error.log
```

## 로그 출력 예시

```json
[2025-11-19 10:30:45] WARNING in interceptors: Client Error Response:
{
  "timestamp": "2025-11-19T10:30:45.123456",
  "method": "POST",
  "url": "http://localhost:8002/auth/login",
  "path": "/auth/login",
  "remote_addr": "127.0.0.1",
  "status_code": 401,
  "headers": {
    "Content-Type": "application/json",
    "Authorization": "Bearer ***"
  },
  "request_body": {
    "username": "testuser",
    "password": "***"
  },
  "response_body": {
    "message": "잘못된 인증 정보입니다"
  }
}
```

## 커스텀 에러 핸들러

### 404 Not Found
자동으로 표준화된 응답 반환:
```json
{
  "message": "요청하신 리소스를 찾을 수 없습니다",
  "path": "/requested/path"
}
```

### 500 Internal Server Error
디버그 모드에 따라 다른 정보 제공:
- **DEBUG=True**: 상세 에러 메시지 포함
- **DEBUG=False**: 일반 에러 메시지만 표시

### 기타 예외
처리되지 않은 모든 예외를 자동으로 캐치하여 로깅

## 보안 고려사항

### 자동 마스킹 필드
다음 필드는 자동으로 `***`로 마스킹됩니다:
- `password`
- `token`
- `Authorization` 헤더

### 추가 마스킹 필요 시
`apps/common/interceptors.py`의 `log_error_response` 함수에서 추가:
```python
if "secret_field" in body:
    body["secret_field"] = "***"
```

## 비활성화 방법

특정 환경에서 인터셉터를 비활성화하려면 `apps/app.py`에서 주석 처리:
```python
# HTTP 인터셉터 및 로깅 설정
# from apps.common.interceptors import register_interceptors, setup_logging
# setup_logging(app)
# register_interceptors(app)
```

## 성능 영향

- 에러 응답에만 로깅 적용 (정상 응답은 오버헤드 없음)
- 비동기 로깅으로 응답 속도에 영향 최소화
- 로그 파일 로테이션으로 디스크 공간 관리

## 문제 해결

### 로그 파일이 생성되지 않음
1. `logs/` 디렉토리 권한 확인
2. 애플리케이션 재시작
3. 에러 응답 발생시키기 (테스트)

### 로그가 너무 많이 쌓임
1. 로그 레벨 조정: `interceptors.py`에서 `setLevel(logging.ERROR)`로 변경
2. 로테이션 설정 조정: `maxBytes`, `backupCount` 값 변경

### 민감한 정보가 로그에 노출됨
1. `log_error_response` 함수에 마스킹 로직 추가
2. 특정 엔드포인트는 로그 제외 처리
