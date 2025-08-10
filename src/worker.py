"""
Celery Worker Entry Point
========================

Entry point for starting Celery workers with proper Flask app context.
"""

import sys
import logging
from pathlib import Path

# Configure logging for worker
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('celery_worker.log')
    ]
)

logger = logging.getLogger(__name__)

def create_worker_app():
    """Create Flask app for Celery worker context."""
    
    # Add project root to path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    # Import after path setup
    from app.factory import create_app, get_celery_app
    
    # Create minimal Flask app for worker
    app = create_app('worker')
    
    # Get Celery instance
    celery = get_celery_app()
    
    # Update Celery with Flask app context
    class ContextTask(celery.Task):
        """Make celery tasks work with Flask app context."""
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery.Task = ContextTask
    
    return app, celery

# Create app and celery instances for worker
app, celery = create_worker_app()

if __name__ == '__main__':
    logger.info("Starting Celery worker...")
    
    # Start worker
    celery.start()
