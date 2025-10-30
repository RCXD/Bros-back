from pathlib import Path
import secrets
from datetime import timedelta

# 기본 경로
basedir = Path(__file__).parent.parent


class Config:
    # 비밀 키 (base64 인코딩 된 무작위 32글자)
    SECRET_KEY = secrets.token_urlsafe(32)
    # DB URI
    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://user2:1234@192.168.0.49:3306/404found"
    # DB 변경 추적(리소스 많이 소모)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # 쿼리문 터미널에 출력
    SQLALCHEMY_ECHO = True
    # CORS 허용 경로
    CORS_ORIGINS = "*"
    # 세션 쿠키는 모든 동일 사이트 및 크로스-사이트 요청과 함께 전송
    SESSION_COOKIE_SAMESITE = "None"
    # 세션 쿠키에 안전한 쿠키만 사용
    SESSION_COOKIE_SECURE = True
    # JWT 암호화 키
    JWT_SECRET_KEY = secrets.token_urlsafe(32)
    # 액세스 토큰 만료 시간: 15분
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    # 리프레시 토큰 만료 시간: 7일
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)
    JWT_TOKEN_LOCATION = ["cookies", "headers"]  # 토큰 위치
    JWT_ACCESS_COOKIE_PATH = "/"  # 접근 가능한 경로
    JWT_REFRESH_COOKIE_PATH = "/token/refresh"
    JWT_COOKIE_CSRF_PROTECT = True  # CSRF 방지 활성화
    JWT_ACCESS_CSRF_HEADER_NAME = "X-CSRF-TOKEN"  # CSRF 토큰 헤더 이름
    JWT_COOKIE_SECURE = True  # 실 사용시엔 True로 설정
    JWT_COOKIE_HTTPONLY = True  # JS로 쿠키 접근 불가
