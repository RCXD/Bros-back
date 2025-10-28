from pathlib import Path
import secrets
from datetime import timedelta

# 기본 경로
basedir = Path(__file__).parent.parent


class Config:
    # 비밀 키 (base64 인코딩 된 무작위 32글자)
    SECRET_KEY = secrets.token_urlsafe(32)
    # DB URI
    SQLALCHEMY_DATABASE_URI = "sqlite:///404found.db"
    # DB 변경 추적(리소스 많이 소모)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # 쿼리문 터미널에 출력
    SQLALCHEMY_ECHO = True
    # CORS 허용 경로
    CORS_ORIGINS = ["http://localhost:5173"]
    # 세션 쿠키는 모든 동일 사이트 및 크로스-사이트 요청과 함께 전송
    SESSION_COOKIE_SAMESITE = "None"
    # 세션 쿠키에 안전한 쿠키만 사용
    SESSION_COOKIE_SECURE = True
    # JWT 암호화 키
    JWT_SECRET_KEY = secrets.token_urlsafe(32)
    # 액세스 토큰 만료 시간: 1시간
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    # 리프레시 토큰 만료 시간: 14일
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=14)
    # 토큰 위치: Authorization 헤더
    JWT_TOKEN_LOCATION = ["headers"]
    # 헤더 이름
    JWT_HEADER_NAME = "Authorization"
    # 토큰 타입
    JWT_HEADER_TYPE = "Bearer"
