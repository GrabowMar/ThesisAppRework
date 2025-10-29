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
    # Ensure we get the src directory regardless of where we run from
    BASE_DIR = Path(__file__).resolve().parent.parent  # This should be /src
    DATABASE_PATH = BASE_DIR / 'data' / 'thesis_app.db'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f'sqlite:///{DATABASE_PATH}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Ensure database directory exists
    DATABASE_PATH.parent.mkdir(exist_ok=True)
    
    # External service URLs
    ANALYZER_BASE_URL = os.environ.get('ANALYZER_BASE_URL', 'http://localhost:8080')
    
    # Model / generation data paths (read-only JSONs & generated dirs)
    MISC_DIR = BASE_DIR.parent / 'misc'
    MODELS_DIR = MISC_DIR / 'models'  # legacy (may be deprecated later)
    PORT_CONFIG_FILE = MISC_DIR / 'port_config.json'
    MODELS_SUMMARY_FILE = MISC_DIR / 'models_summary.json'

    # Unified generated apps root (mirrors app.paths.GENERATED_APPS_DIR)
    GENERATED_APPS_DIR = BASE_DIR / 'generated' / 'apps'
    
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
    
    # Celery settings for better error handling
    CELERY_TASK_ALWAYS_EAGER = os.environ.get('CELERY_ALWAYS_EAGER', 'False').lower() == 'true'
    CELERY_TASK_EAGER_PROPAGATES = True
    CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
    CELERY_BROKER_CONNECTION_RETRY = True
    CELERY_RESULT_BACKEND_TRANSPORT_OPTIONS = {
        'retry_on_timeout': True,
        'visibility_timeout': 3600,
        'fanout_prefix': True,
        'fanout_patterns': True
    }
    
    # Celery worker configuration (solo pool for Windows, threads for Linux)
    CELERY_WORKER_POOL = os.environ.get('CELERY_WORKER_POOL', 'solo' if os.name == 'nt' else 'prefork')
    CELERY_WORKER_CONCURRENCY = int(os.environ.get('CELERY_WORKER_CONCURRENCY', '1'))
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TIMEZONE = 'UTC'
    CELERY_ENABLE_UTC = True
    
    # Analyzer Service Configuration
    # Timeout for individual analyzer services (seconds)
    # If a service takes longer than this, it will be marked as failed but analysis continues
    ANALYZER_SERVICE_TIMEOUT = int(os.environ.get('ANALYZER_SERVICE_TIMEOUT', '600'))  # 10 minutes default
    
    # Whether to retry failed analyzer services (default: no retry for faster feedback)
    ANALYZER_RETRY_FAILED_SERVICES = os.environ.get('ANALYZER_RETRY_FAILED_SERVICES', 'false').lower() == 'true'
    
    # Security Analysis Tool Configurations
    SECURITY_ANALYZER_CONFIG = {
        'bandit': {
            'enabled': True,
            'confidence_level': 'HIGH',  # LOW, MEDIUM, HIGH
            'severity_level': 'LOW',     # LOW, MEDIUM, HIGH
            'exclude_paths': [
                '*/tests/*',
                '*/test_*',
                '*/migrations/*',
                '*/venv/*',
                '*/node_modules/*'
            ],
            'skipped_tests': [
                'B101',  # Test for use of assert
                'B601',  # Shell injection (paramiko)
            ],
            'formats': ['json', 'txt'],
            'baseline_file': None,  # Path to baseline file if needed
            'timeout': 300  # seconds
        },
        'safety': {
            'enabled': True,
            'database_path': None,  # Use default vulnerability database
            'ignore_ids': [],  # List of vulnerability IDs to ignore
            'output_format': 'json',
            'check_unpinned': True,  # Check for unpinned dependencies
            'timeout': 180
        },
        'pylint': {
            'enabled': True,
            'rcfile': None,  # Path to pylintrc config file
            'disable': [
                'C0103',  # Invalid name
                'R0903',  # Too few public methods
                'W0613',  # Unused argument
            ],
            'enable': [
                'W0622',  # Redefined builtin
            ],
            'output_format': 'json',
            'confidence': 'HIGH',
            'timeout': 300
        },
        'eslint': {
            'enabled': True,
            'config_file': None,  # Path to .eslintrc file
            'rules': {
                'security/detect-object-injection': 'error',
                'security/detect-non-literal-fs-filename': 'error',
                'security/detect-unsafe-regex': 'error',
                'security/detect-buffer-noassert': 'error',
                'security/detect-eval-with-expression': 'error',
                'security/detect-no-csrf-before-method-override': 'error',
                'security/detect-pseudoRandomBytes': 'error'
            },
            'plugins': ['security'],
            'output_format': 'json',
            'max_warnings': 50,
            'timeout': 240
        },
        'zap': {
            'enabled': True,
            'api_key': None,  # ZAP API key
            'daemon_mode': True,
            'host': 'localhost',
            'port': 8080,
            'scan_types': {
                'spider': {
                    'enabled': True,
                    'max_depth': 5,
                    'max_duration': 600,  # 10 minutes
                    'user_agent': 'ZAP/2.14.0'
                },
                'active_scan': {
                    'enabled': True,
                    'policy': 'Default Policy',
                    'max_duration': 1800,  # 30 minutes
                    'max_rule_duration': 300,  # 5 minutes per rule
                    'delay_in_ms': 0
                },
                'passive_scan': {
                    'enabled': True,
                    'max_alerts_per_rule': 10
                }
            },
            'authentication': {
                'method': 'form',  # form, script, manual
                'login_url': None,
                'username_field': 'username',
                'password_field': 'password',
                'username': None,
                'password': None,
                'logged_in_regex': None,
                'logged_out_regex': None
            },
            'context': {
                'name': 'Default Context',
                'include_urls': ['.*'],
                'exclude_urls': [
                    '.*logout.*',
                    '.*signout.*',
                    '.*admin.*'
                ]
            },
            'reporting': {
                'formats': ['json', 'html', 'xml'],
                'include_passed': False,
                'confidence_threshold': 'Medium',  # High, Medium, Low
                'risk_threshold': 'Low'  # High, Medium, Low, Informational
            },
            'timeout': 3600  # 1 hour max for full scan
        }
    }
    
    # Performance Analysis Tool Configurations
    PERFORMANCE_ANALYZER_CONFIG = {
        'lighthouse': {
            'enabled': True,
            'categories': ['performance', 'accessibility', 'best-practices', 'seo'],
            'device': 'mobile',  # mobile, desktop
            'throttling': {
                'cpu_slowdown': 4,
                'network_throttling': '3G'  # 3G, 4G, cable, none
            },
            'chrome_flags': [
                '--headless',
                '--disable-gpu',
                '--no-sandbox',
                '--disable-dev-shm-usage'
            ],
            'output_format': 'json',
            'timeout': 300
        },
        'load_testing': {
            'enabled': True,
            'tool': 'locust',  # locust, artillery, ab
            'concurrent_users': 10,
            'spawn_rate': 2,  # users per second
            'duration': 60,  # seconds
            'target_paths': [
                '/',
                '/api/health',
                '/login',
                '/dashboard'
            ],
            'timeout': 600
        },
        'resource_monitoring': {
            'enabled': True,
            'metrics': ['cpu', 'memory', 'disk', 'network'],
            'interval': 5,  # seconds
            'duration': 300,  # seconds
            'thresholds': {
                'cpu_percent': 80,
                'memory_percent': 85,
                'disk_percent': 90
            }
        }
    }
    
    # AI Analysis Tool Configurations  
    AI_ANALYZER_CONFIG = {
        'code_quality': {
            'enabled': True,
            'model': 'gpt-4o-mini',
            'temperature': 0.1,
            'max_tokens': 2000,
            'analysis_types': [
                'readability',
                'maintainability', 
                'design_patterns',
                'best_practices',
                'code_smells'
            ],
            'context_window': 8000,
            'timeout': 180
        },
        'security_review': {
            'enabled': True,
            'model': 'gpt-4o',
            'temperature': 0.0,
            'max_tokens': 1500,
            'focus_areas': [
                'input_validation',
                'authentication',
                'authorization',
                'data_handling',
                'crypto_usage',
                'error_handling'
            ],
            'severity_scoring': True,
            'timeout': 240
        },
        'architecture_analysis': {
            'enabled': True,
            'model': 'claude-3-sonnet',
            'temperature': 0.2,
            'max_tokens': 3000,
            'analysis_scope': [
                'component_structure',
                'dependency_graph',
                'scalability',
                'performance_implications',
                'technical_debt'
            ],
            'include_diagrams': True,
            'timeout': 300
        }
    }


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TESTING = False
    
    # Use existing analyzer Redis container
    # Redis is running in analyzer-redis-1 container on localhost:6379
    CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    
    # Disable eager execution to use actual Redis
    CELERY_TASK_ALWAYS_EAGER = os.environ.get('CELERY_ALWAYS_EAGER', 'False').lower() == 'true'
    
    # Additional development settings
    CELERY_TASK_EAGER_PROPAGATES = True
    CELERY_CACHE_BACKEND = 'redis'
    
    # Development logging
    LOG_LEVEL = 'DEBUG'


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DEBUG = True
    # Use in-memory database for tests
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    # Always use eager execution in testing
    CELERY_TASK_ALWAYS_EAGER = True


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
