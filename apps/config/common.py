"""
Common configuration shared across all modules
"""
from pathlib import Path
import secrets
from datetime import timedelta
import os

# Base directory
basedir = Path(__file__).parent.parent.parent


class Config:
    """Base configuration class"""
    
    # Security
    SECRET_KEY = secrets.token_urlsafe(32)
    
    # Database
    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:1234@localhost:3306/404found"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = True
    
    # CORS
    CORS_ORIGINS = "*"
    
    # Session
    SESSION_COOKIE_SAMESITE = "None"
    SESSION_COOKIE_SECURE = True
    
    # JWT
    JWT_SECRET_KEY = secrets.token_urlsafe(32)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=5)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=60)
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_NAME = "Authorization"
    JWT_HEADER_TYPE = "Bearer"
    
    # AI Server URLs
    AI_OBJECT_DETECTION_URL = "http://192.168.1.79:8888"
    AI_ROAD_BOUNDARY_URL = "http://192.168.1.79:8889"
    OPENSTREET_URL = "http://192.168.1.79:8890"
    
    # Static files
    STATIC_FOLDER = "static"
    STATIC_URL_PATH = "/static"

    CID = "TC0ONETIME"
    # 관리자 키 (환경변수 권장)
    KAKAO_ADMIN_KEY = os.getenv("KAKAO_ADMIN_KEY")
    KAKAO_APPROVAL_URL = os.getenv(
        "KAKAO_APPROVAL_URL",
        "http://localhost:5000/payment/approve"    # 카카오에서 다시 돌아오는 URL
    )
    KAKAO_CANCEL_URL = os.getenv(
        "KAKAO_CANCEL_URL",
        "http://localhost:3000/payment/cancel"     # 프론트 전용 취소 페이지
    )
    KAKAO_FAIL_URL = os.getenv(
        "KAKAO_FAIL_URL",
        "http://localhost:3000/payment/fail"       # 프론트 전용 실패 페이지
    )

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SQLALCHEMY_ECHO = True


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SQLALCHEMY_ECHO = False


class TestConfig(Config):
    """Test configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:1234@localhost:3306/404found_test"
    SQLALCHEMY_ECHO = False


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'test': TestConfig,
    'default': DevelopmentConfig
}
