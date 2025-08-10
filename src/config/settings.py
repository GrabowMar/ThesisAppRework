"""
Application Configuration
========================

Configuration settings for different environments.
"""

import os
from pathlib import Path


class Config:
    """Base configuration class."""
    
    # Basic Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Database settings
    BASE_DIR = Path(__file__).parent.parent
    DATABASE_PATH = BASE_DIR / 'data' / 'thesis_app.db'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f'sqlite:///{DATABASE_PATH}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # External service URLs
    ANALYZER_BASE_URL = os.environ.get('ANALYZER_BASE_URL', 'http://localhost:8080')
    
    # Model data paths (read-only)
    MISC_DIR = BASE_DIR.parent / 'misc'
    MODELS_DIR = MISC_DIR / 'models'
    PORT_CONFIG_FILE = MISC_DIR / 'port_config.json'
    MODEL_CAPABILITIES_FILE = MISC_DIR / 'model_capabilities.json'
    
    # Analyzer paths
    ANALYZER_DIR = BASE_DIR.parent / 'analyzer'
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = BASE_DIR / 'logs' / 'app.log'
    
    # HTMX settings
    HTMX_VERSION = '1.9.10'
    
    # Pagination
    ITEMS_PER_PAGE = 20
    
    # Background tasks
    CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TESTING = False


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DEBUG = True
    # Use in-memory database for tests
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False
    
    def __init__(self):
        super().__init__()
        # Production database should be set via environment variable
        if not os.environ.get('DATABASE_URL'):
            raise ValueError("DATABASE_URL environment variable is required for production")
        self.SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')


# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
