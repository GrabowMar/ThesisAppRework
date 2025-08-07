"""
Celery Configuration for Background Task Processing
=================================================

Configuration for Celery task queue system with Redis backend.
Handles long-running analysis tasks asynchronously.
"""

import os
from kombu import Queue

# Redis configuration
BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Task configuration
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TIMEZONE = 'UTC'
CELERY_ENABLE_UTC = True

# Task routing
CELERY_ROUTES = {
    'src.tasks.run_security_analysis_task': {'queue': 'security_analysis'},
    'src.tasks.run_performance_test_task': {'queue': 'performance_testing'},
    'src.tasks.run_zap_scan_task': {'queue': 'zap_scanning'},
    'src.tasks.run_openrouter_analysis_task': {'queue': 'ai_analysis'},
    'src.tasks.run_batch_analysis_task': {'queue': 'batch_processing'},
}

# Queue configuration
CELERY_QUEUES = (
    Queue('security_analysis', routing_key='security_analysis'),
    Queue('performance_testing', routing_key='performance_testing'),
    Queue('zap_scanning', routing_key='zap_scanning'),
    Queue('ai_analysis', routing_key='ai_analysis'),
    Queue('batch_processing', routing_key='batch_processing'),
    Queue('celery', routing_key='celery'),  # Default queue
)

# Worker configuration
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_MAX_TASKS_PER_CHILD = 10
CELERY_WORKER_DISABLE_RATE_LIMITS = False

# Task execution configuration
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 3600  # 1 hour max per task
CELERY_TASK_SOFT_TIME_LIMIT = 3000  # 50 minutes soft limit
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_SEND_TASK_EVENTS = True

# Result backend configuration
CELERY_RESULT_EXPIRES = 3600  # Results expire after 1 hour
CELERY_RESULT_PERSISTENT = True

# Monitoring configuration
CELERY_SEND_EVENTS = True
CELERY_SEND_TASK_SENT_EVENT = True

# Error handling
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_IGNORE_RESULT = False

# Retry configuration
CELERY_TASK_DEFAULT_RETRY_DELAY = 60  # 1 minute
CELERY_TASK_MAX_RETRIES = 3

# Security
CELERY_WORKER_HIJACK_ROOT_LOGGER = False
CELERY_WORKER_LOG_COLOR = False

# Beat schedule for periodic tasks (if needed)
CELERYBEAT_SCHEDULE = {
    'cleanup-expired-results': {
        'task': 'src.tasks.cleanup_expired_results',
        'schedule': 3600.0,  # Run every hour
    },
    'health-check-containers': {
        'task': 'src.tasks.health_check_containers',
        'schedule': 300.0,  # Run every 5 minutes
    },
}
