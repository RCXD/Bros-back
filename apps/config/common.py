"""
Common configuration shared across all modules
Loads configuration from environment variables (.env.local or .env.production)
"""
from pathlib import Path
import os
from datetime import timedelta
from dotenv import load_dotenv

# Base directory
basedir = Path(__file__).parent.parent.parent

# Load environment variables
env_file = basedir / '.env.local'
if not env_file.exists():
    env_file = basedir / '.env.production'
if not env_file.exists():
    env_file = basedir / '.env'

load_dotenv(env_file)


def get_bool(key, default=False):
    """Convert environment variable string to boolean"""
    value = os.getenv(key, str(default)).lower()
    return value in ('true', '1', 'yes', 'on')


def get_int(key, default=0):
    """Convert environment variable string to integer"""
    try:
        return int(os.getenv(key, default))
    except (ValueError, TypeError):
        return default


class Config:
    """Base configuration class"""
    
    # Security
    SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(32).hex())
    
    # Database
    DB_USER = os.getenv('DB_USER', 'user1')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '1234')
    DB_HOST = os.getenv('DB_HOST', '192.168.1.79')
    DB_PORT = os.getenv('DB_PORT', '3306')
    DB_NAME = os.getenv('DB_NAME', '404found_test1')
    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    SQLALCHEMY_TRACK_MODIFICATIONS = get_bool('SQLALCHEMY_TRACK_MODIFICATIONS', False)
    SQLALCHEMY_ECHO = get_bool('SQLALCHEMY_ECHO', True)
    
    # CORS
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*')
    
    # Session
    SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', 'None')
    SESSION_COOKIE_SECURE = get_bool('SESSION_COOKIE_SECURE', True)
    
    # JWT
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', os.urandom(32).hex())
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=get_int('JWT_ACCESS_TOKEN_EXPIRES_HOURS', 5))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=get_int('JWT_REFRESH_TOKEN_EXPIRES_DAYS', 60))
    JWT_TOKEN_LOCATION = [os.getenv('JWT_TOKEN_LOCATION', 'headers')]
    JWT_HEADER_NAME = os.getenv('JWT_HEADER_NAME', 'Authorization')
    JWT_HEADER_TYPE = os.getenv('JWT_HEADER_TYPE', 'Bearer')
    
    # AI Server URLs
    AI_OBJECT_DETECTION_URL = os.getenv('AI_OBJECT_DETECTION_URL', 'http://192.168.1.79:8888')
    AI_ROAD_BOUNDARY_URL = os.getenv('AI_ROAD_BOUNDARY_URL', 'http://192.168.1.79:8889')
    OPENSTREET_URL = os.getenv('OPENSTREET_URL', 'http://192.168.1.79:8890')
    
    # Roadview API Keys
    GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', '')
    KAKAO_REST_API_KEY = os.getenv('KAKAO_REST_API_KEY', '')
    NAVER_CLIENT_ID = os.getenv('NAVER_CLIENT_ID', '')
    NAVER_CLIENT_SECRET = os.getenv('NAVER_CLIENT_SECRET', '')
    
    # File Upload
    MAX_CONTENT_LENGTH = get_int('MAX_CONTENT_LENGTH_MB', 16) * 1024 * 1024
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'app/static')
    
    # Static files
    STATIC_FOLDER = os.getenv('STATIC_FOLDER', 'static')
    STATIC_URL_PATH = os.getenv('STATIC_URL_PATH', '/static')


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = get_bool('FLASK_DEBUG', True)
    SQLALCHEMY_ECHO = get_bool('SQLALCHEMY_ECHO', True)


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = get_bool('FLASK_DEBUG', False)
    SQLALCHEMY_ECHO = get_bool('SQLALCHEMY_ECHO', False)


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
