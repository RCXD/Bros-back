"""
모든 모듈에서 공유하는 공통 설정
환경 변수 파일에서 설정을 로드합니다 (.env.local 또는 .env.production)
"""

from pathlib import Path
import os
from datetime import timedelta
from dotenv import load_dotenv

# 기본 디렉토리
basedir = Path(__file__).parent.parent.parent

# 환경 변수 로드
env_file = basedir / ".env.local"
if not env_file.exists():
    env_file = basedir / ".env.production"
if not env_file.exists():
    env_file = basedir / ".env"

load_dotenv(env_file)


def get_bool(key: str, default: bool = False) -> bool:
    """Read an environment variable and coerce it to a boolean.

    Truthy strings are ``"true"``, ``"1"``, ``"yes"``, and ``"on"``
    (case-insensitive).  Everything else is considered ``False``.

    Args:
        key: Name of the environment variable.
        default: Value to use when the variable is not set.

    Returns:
        The boolean interpretation of the environment variable's value.
    """
    value = os.getenv(key, str(default)).lower()
    return value in ("true", "1", "yes", "on")


def get_int(key: str, default: int = 0) -> int:
    """Read an environment variable and coerce it to an integer.

    Returns *default* if the variable is not set or cannot be parsed as
    an integer.

    Args:
        key: Name of the environment variable.
        default: Value to use when the variable is absent or invalid.

    Returns:
        The integer interpretation of the environment variable's value.
    """
    try:
        return int(os.getenv(key, default))
    except (ValueError, TypeError):
        return default


class Config:
    """Base configuration class shared by all environments.

    All settings are read from environment variables (loaded from
    ``.env.local``, ``.env.production``, or ``.env`` in that order).
    Sensible defaults are provided for local development.
    """

    # 보안
    SECRET_KEY = os.getenv("SECRET_KEY", os.urandom(32).hex())

    # Database
    DB_USER = os.getenv("DB_USER", "user1")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "1234")
    DB_HOST = os.getenv("DB_HOST", "192.168.1.79")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_NAME = os.getenv("DB_NAME", "404found_test2")
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = get_bool("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    SQLALCHEMY_ECHO = get_bool("SQLALCHEMY_ECHO", False)

    print(SQLALCHEMY_DATABASE_URI)

    # CORS
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

    # IP 닉네임 매핑 (로그용)
    IP_NICKNAMES = {
        "192.168.1.89": "MASTER",
        "192.168.1.79": "SLAVE",
        "192.168.1.86": "SUBMISIVE",
        "192.168.1.83": "WOOSIK_PT",
        "192.168.1.82": "SU_KARINA",
        "192.168.1.78": "YUNJAE_GOD",
        "192.168.1.87": "TAK_BEAR",
        "127.0.0.1": "LOCAL",
        "::1": "LOCAL",
        # 필요한 IP 추가
    }

    # Session
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "None")
    SESSION_COOKIE_SECURE = get_bool("SESSION_COOKIE_SECURE", True)

    # JWT
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", os.urandom(32).hex())
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        hours=get_int("JWT_ACCESS_TOKEN_EXPIRES_HOURS", 5)
    )
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        days=get_int("JWT_REFRESH_TOKEN_EXPIRES_DAYS", 60)
    )
    JWT_TOKEN_LOCATION = [os.getenv("JWT_TOKEN_LOCATION", "headers")]
    JWT_HEADER_NAME = os.getenv("JWT_HEADER_NAME", "Authorization")
    JWT_HEADER_TYPE = os.getenv("JWT_HEADER_TYPE", "Bearer")

    # AI Server URLs
    AI_OBJECT_DETECTION_URL = os.getenv(
        "AI_OBJECT_DETECTION_URL", "http://192.168.1.79:8888"
    )
    AI_ROAD_BOUNDARY_URL = os.getenv("AI_ROAD_BOUNDARY_URL", "http://192.168.1.79:8889")
    OPENSTREET_URL = os.getenv("OPENSTREET_URL", "http://192.168.1.79:8890")

    # Roadview API Keys
    GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
    KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "")
    NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
    NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")

    # File Upload
    MAX_CONTENT_LENGTH = get_int("MAX_CONTENT_LENGTH_MB", 16) * 1024 * 1024
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "app/static")

    # Static files
    STATIC_FOLDER = os.getenv("STATIC_FOLDER", "static")
    STATIC_URL_PATH = os.getenv("STATIC_URL_PATH", "/static")

    CID = "TC0ONETIME"
    # 관리자 키 (환경변수 권장)
    KAKAO_ADMIN_KEY = os.getenv("KAKAO_ADMIN_KEY")
    KAKAO_APPROVAL_URL = os.getenv(
        "KAKAO_APPROVAL_URL",
        "http://localhost:5173/payment/success",  # 카카오에서 다시 돌아오는 URL
    )
    KAKAO_CANCEL_URL = os.getenv(
        "KAKAO_CANCEL_URL",
        "http://localhost:3000/payment/cancel",  # 프론트 전용 취소 페이지
    )
    KAKAO_FAIL_URL = os.getenv(
        "KAKAO_FAIL_URL",
        "http://localhost:3000/payment/fail",  # 프론트 전용 실패 페이지
    )


class DevelopmentConfig(Config):
    """Development environment configuration.

    Enables debug mode by default and configures SQLAlchemy echo based
    on the ``SQLALCHEMY_ECHO`` environment variable.
    """

    DEBUG = get_bool("FLASK_DEBUG", True)
    SQLALCHEMY_ECHO = get_bool("SQLALCHEMY_ECHO", False)


class ProductionConfig(Config):
    """Production environment configuration.

    Disables debug mode and SQLAlchemy echo by default to reduce
    verbosity and protect sensitive information in production.
    """

    DEBUG = get_bool("FLASK_DEBUG", False)
    SQLALCHEMY_ECHO = get_bool("SQLALCHEMY_ECHO", False)


class TestConfig(Config):
    """Test environment configuration.

    Uses a separate test database and disables SQLAlchemy echo to keep
    test output clean.
    """

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:1234@localhost:3306/404found_test"
    SQLALCHEMY_ECHO = False


# 설정 딕셔너리
config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "test": TestConfig,
    "default": DevelopmentConfig,
}
