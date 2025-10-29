"""
Celery Configuration for AI Research Platform
===========================================

Configuration for Celery task queue system with Redis backend.
Handles long-running analysis tasks asynchronously with the analyzer infrastructure.
"""

import os
from kombu import Queue


class CeleryConfig:
    """Celery configuration class."""
    
    # Redis configuration
    broker_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    result_backend = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    # Mitigate startup connection warnings
    broker_connection_retry_on_startup = True
    
    # Beat schedule for periodic tasks - reduced frequencies to minimize spam
    beat_schedule = {
        'cleanup-expired-results': {
            'task': 'app.tasks.cleanup_expired_results',
            'schedule': 3600.0,  # Run every hour
        },
        'health-check-analyzers': {
            'task': 'app.tasks.health_check_analyzers',
            'schedule': 600.0,  # Run every 10 minutes (reduced frequency)
        },
        'monitor-analyzer-containers': {
            'task': 'app.tasks.monitor_analyzer_containers',
            'schedule': 300.0,  # Run every 5 minutes (reduced from 1 minute to reduce spam)
        },
    }



# Legacy configuration variables for backward compatibility
BROKER_URL = CeleryConfig.broker_url
CELERY_RESULT_BACKEND = CeleryConfig.result_backend

# Task configuration
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TIMEZONE = 'UTC'
CELERY_ENABLE_UTC = True

# Task routing
CELERY_ROUTES = {
    'app.tasks.security_analysis_task': {'queue': 'security_analysis'},
    'app.tasks.performance_test_task': {'queue': 'performance_testing'},
    'app.tasks.static_analysis_task': {'queue': 'static_analysis'},
    'app.tasks.dynamic_analysis_task': {'queue': 'dynamic_analysis'},
    'app.tasks.ai_analysis_task': {'queue': 'ai_analysis'},
    'app.tasks.batch_analysis_task': {'queue': 'batch_processing'},
    'app.tasks.container_management_task': {'queue': 'container_ops'},
    'app.tasks.health_check_task': {'queue': 'monitoring'},
    # Parallel subtask routing
    'app.tasks.run_static_analyzer_subtask': {'queue': 'subtasks'},
    'app.tasks.run_dynamic_analyzer_subtask': {'queue': 'subtasks'},
    'app.tasks.run_performance_tester_subtask': {'queue': 'subtasks'},
    'app.tasks.run_ai_analyzer_subtask': {'queue': 'subtasks'},
    'app.tasks.aggregate_subtask_results': {'queue': 'aggregation'},
}

# Queue configuration
CELERY_QUEUES = (
    Queue('security_analysis', routing_key='security_analysis'),
    Queue('performance_testing', routing_key='performance_testing'),
    Queue('static_analysis', routing_key='static_analysis'),
    Queue('dynamic_analysis', routing_key='dynamic_analysis'),
    Queue('ai_analysis', routing_key='ai_analysis'),
    Queue('batch_processing', routing_key='batch_processing'),
    Queue('container_ops', routing_key='container_ops'),
    Queue('monitoring', routing_key='monitoring'),
    Queue('subtasks', routing_key='subtasks'),  # Parallel subtask queue
    Queue('aggregation', routing_key='aggregation'),  # Result aggregation queue
    Queue('celery', routing_key='celery'),  # Default queue
)

# Worker configuration
CELERY_WORKER_PREFETCH_MULTIPLIER = 4  # Allow prefetch for parallel execution
CELERY_WORKER_MAX_TASKS_PER_CHILD = 50
CELERY_WORKER_DISABLE_RATE_LIMITS = False

# Windows-specific configuration - use threads for parallel execution
CELERY_WORKER_POOL = 'threads'  # Use thread pool for Windows compatibility and parallelism
CELERY_WORKER_CONCURRENCY = 8  # Allow 8 concurrent subtasks (2 full analyses in parallel)

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

# Beat schedule for periodic tasks
CELERYBEAT_SCHEDULE = {
    'cleanup-expired-results': {
        'task': 'app.tasks.cleanup_expired_results',
        'schedule': 3600.0,  # Run every hour
    },
    'health-check-analyzers': {
        'task': 'app.tasks.health_check_analyzers',
        'schedule': 600.0,  # Run every 10 minutes (reduced frequency)
    },
    'monitor-analyzer-containers': {
        'task': 'app.tasks.monitor_analyzer_containers',
        'schedule': 300.0,  # Run every 5 minutes (reduced from 1 minute to reduce spam)
    },
}

# Analysis-specific configuration
ANALYZER_CONFIG = {
    'services': {
        'static-analyzer': {
            'host': 'localhost',
            'port': 8001,
            'websocket_url': 'ws://localhost:8001/ws',
            'timeout': 300,
        },
        'security-analyzer': {
            'host': 'localhost', 
            'port': 8002,
            'websocket_url': 'ws://localhost:8002/ws',
            'timeout': 600,
        },
        'performance-tester': {
            'host': 'localhost',
            'port': 8003,
            'websocket_url': 'ws://localhost:8003/ws',
            'timeout': 900,
        },
        'ai-analyzer': {
            'host': 'localhost',
            'port': 8004,
            'websocket_url': 'ws://localhost:8004/ws',
            'timeout': 1200,
        },
    },
    'analyzer_manager_path': '../../analyzer/analyzer_manager.py',
    'default_timeout': 300,
    'max_retries': 3,
    'retry_delay': 60,
}
