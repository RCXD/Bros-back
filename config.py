"""
Configuration settings for Flask application.
Supports different environments (development, production).
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()


class Config:
    """Base configuration class."""
    
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # CORS settings
    # Allow React development server and production URLs
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '').split(',') if os.environ.get('CORS_ORIGINS') else [
        'http://localhost:3000',  # React default dev server
        'http://localhost:5173',  # Vite default dev server
        'http://127.0.0.1:3000',
        'http://127.0.0.1:5173',
    ]
    
    # API settings
    JSON_SORT_KEYS = False
    
    # Database settings (placeholder for future use)
    DATABASE_URL = os.environ.get('DATABASE_URL')


class DevelopmentConfig(Config):
    """Development environment configuration."""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Production environment configuration."""
    DEBUG = False
    TESTING = False


class TestingConfig(Config):
    """Testing environment configuration."""
    DEBUG = True
    TESTING = True


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
