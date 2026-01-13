"""
Celery Worker Entry Point
=========================

Initializes the Celery application with Flask context.
Supports isolation for parallel test execution via Redis database selection.

IMPORTANT: Background services (like PipelineExecutionService) are started via
Celery signals AFTER fork, not during create_app(). This is because daemon threads
don't survive process fork in Celery's prefork execution model.
"""

import os
import threading
from celery import Celery
from celery.signals import worker_process_init
from app.factory import create_app
from app.utils.redis_isolation import get_isolation_aware_redis_url

# Track if pipeline service has been started in this worker process
_pipeline_service_started = False
_pipeline_service_lock = threading.Lock()

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


@worker_process_init.connect
def init_worker_process(**kwargs):
    """Initialize background services after Celery worker process fork.
    
    Celery uses prefork model where the main process forks worker processes.
    Daemon threads (like PipelineExecutionService) don't survive fork, so we
    must start them AFTER fork in each worker process.
    
    We use atomic file creation (O_CREAT|O_EXCL) to ensure only ONE worker 
    starts the pipeline service. This is race-condition safe.
    """
    global _pipeline_service_started
    
    enable_pipeline_svc = os.environ.get('ENABLE_PIPELINE_SERVICE', 'false').lower() == 'true'
    
    if not enable_pipeline_svc:
        return
    
    with _pipeline_service_lock:
        if _pipeline_service_started:
            return
        
        try:
            import time
            
            # Use atomic file creation - O_CREAT|O_EXCL fails if file exists
            lock_file_path = '/tmp/thesis_pipeline_service.lock'
            
            # First, cleanup stale lock file (from previous container restart)
            # A lock is stale if:
            # 1. The PID in the file is dead, OR
            # 2. The lock file is older than 60 seconds (covers container restart where PIDs recycle)
            try:
                lock_stat = os.stat(lock_file_path)
                lock_age = time.time() - lock_stat.st_mtime
                
                with open(lock_file_path, 'r') as f:
                    old_pid = int(f.read().strip())
                
                # If lock is very old (>60s), it's definitely stale (container restarted)
                if lock_age > 60:
                    print(f"[WORKER PID {os.getpid()}] Removing stale lock (age={lock_age:.1f}s)")
                    os.unlink(lock_file_path)
                else:
                    # Lock is recent - check if process is alive
                    try:
                        os.kill(old_pid, 0)  # Signal 0 = just check existence
                        # Process exists and lock is recent - lock is valid
                        return
                    except OSError:
                        # Process dead - remove stale lock
                        print(f"[WORKER PID {os.getpid()}] Removing stale lock (PID {old_pid} dead)")
                        os.unlink(lock_file_path)
                        
            except (FileNotFoundError, ValueError):
                # No lock file or invalid content - proceed
                pass
            except Exception as e:
                # Error checking lock - try to remove it
                print(f"[WORKER PID {os.getpid()}] Error checking lock file, attempting removal: {e}")
                try:
                    os.unlink(lock_file_path)
                except:
                    pass
            
            # Try to atomically create the lock file
            try:
                fd = os.open(lock_file_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
            except FileExistsError:
                # Another worker beat us to it
                return
            
            # Small delay to ensure we won the race (other workers check the PID)
            time.sleep(0.1)
            
            # Verify we still own the lock
            try:
                with open(lock_file_path, 'r') as f:
                    lock_pid = int(f.read().strip())
                if lock_pid != os.getpid():
                    return  # Someone else owns it now
            except:
                return  # Something went wrong, don't start
            
            # Start the pipeline service
            with flask_app.app_context():
                from app.services.pipeline_execution_service import init_pipeline_execution_service
                from app.utils.logging_config import get_logger
                logger = get_logger('celery_worker')
                
                pipeline_svc = init_pipeline_execution_service(app=flask_app)
                _pipeline_service_started = True
                logger.info(f"[WORKER PID {os.getpid()}] Pipeline execution service started (poll_interval={pipeline_svc.poll_interval}s)")
                
        except Exception as e:
            import traceback
            print(f"[WORKER PID {os.getpid()}] Failed to start pipeline service: {e}")
            traceback.print_exc()
