"""
Celery Worker Entry Point
=========================

Initializes the Celery application with Flask context.
Supports isolation for parallel test execution via Redis database selection.
"""

import os
from celery import Celery
from app.factory import create_app
from app.utils.redis_isolation import get_isolation_aware_redis_url

def make_celery(app):
    """Create and configure Celery instance."""
    celery = Celery(
        app.import_name,
        backend=app.config.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
        broker=app.config.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    )
    
    # Create a new config dictionary with lowercase keys for Celery 5.x/6.x compliance
    # This avoids "ImproperlyConfigured: Cannot mix new and old setting keys"
    celery_config = {}
    for key, value in app.config.items():
        if key.startswith('CELERY_'):
            # Convert CELERY_BROKER_URL to broker_url, etc.
            new_key = key[7:].lower()
            celery_config[new_key] = value
    
    # Explicitly remove any existing uppercase keys from celery.conf to prevent mixing
    for key in list(celery.conf.keys()):
        if key.startswith('CELERY_'):
            del celery.conf[key]
            
    celery.conf.update(celery_config)
    
    # Fix Celery 6.x deprecation warning for broker connection retry
    celery.conf.broker_connection_retry_on_startup = True
    
    # Ensure tasks are discovered
    celery.conf.imports = ('app.tasks',)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery

# Create Flask app instance
flask_app = create_app()

# Ensure Celery config is present (defaults if not in .env)
# Check REDIS_URL first as it's the standard in our docker-compose setup
base_redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# Use isolation-aware Redis URLs (different DB for parallel tests)
# This ensures test sessions don't interfere with each other's task queues
broker_url = get_isolation_aware_redis_url(
    os.environ.get('CELERY_BROKER_URL', base_redis_url)
)
result_backend = get_isolation_aware_redis_url(
    os.environ.get('CELERY_RESULT_BACKEND', base_redis_url)
)

flask_app.config.setdefault('CELERY_BROKER_URL', broker_url)
flask_app.config.setdefault('CELERY_RESULT_BACKEND', result_backend)

# Create Celery app instance
celery = make_celery(flask_app)
