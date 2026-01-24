import os
import sys
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure we can import from app
sys.path.insert(0, "/app/src")
sys.path.insert(0, "/app")

# Set environment variables if needed (though docker exec should inherit container env)
os.environ["FLASK_ENV"] = "development"

try:
    from app import create_app
    from app.extensions import db
    from app.models.user import User
    from app.models.pipeline import PipelineExecution

    app = create_app()

    with app.app_context():
        # Get user
        user = User.query.first()
        if not user:
            logger.info("Creating dummy user")
            user = User(username="admin", email="admin@example.com")
            user.set_password("admin")
            db.session.add(user)
            db.session.commit()
        
        logger.info(f"Triggering pipeline for user: {user.username} (ID: {user.id})")
        
        # Config for concurrent testing
        config = {
            "generation": {
                "mode": "generate",
                # Use a reliable model that is likely available. 
                # Same model twice to test concurrency
                "models": ["google/gemini-2.0-flash-exp:free", "google/gemini-2.0-flash-exp:free"],
                "templates": ["react-flask"],
                "options": {
                    "parallel": True,
                    "maxConcurrentTasks": 2
                }
            },
            "analysis": {
                "enabled": True,
                "tools": ["static-analyzer"], # Use service name or tool name?
                # pipeline_service checks for 'static-analyzer' in STATIC_ANALYSIS_TOOLS list or similar.
                # Actually, config usually uses "static-analysis" or similar.
                # Let's check generated config or default. 
                # But 'static-analyzer' service is running.
                # Let's use ["bandit", "semgrep"] which are static tools, or ["static-analysis"].
                # app/services/pipeline_execution_service.py checks:
                # STATIC_ANALYSIS_TOOLS = {'semgrep', 'bandit', ...}
                # And it checks _requires_analyzer_containers.
                # If I want to test ConcurrentAnalysisRunner with containers, I should use a dynamic tool?
                # "dynamic-analyzer"?
                # But let's start simple.
                "tools": ["semgrep", "bandit"], 
                "options": {
                    "maxConcurrentTasks": 2,
                    "autoStartContainers": True
                }
            }
        }
        
        pipeline = PipelineExecution(
            user_id=user.id,
            config=config,
            name=f"Concurrent Test {datetime.now().strftime('%H:%M:%S')}"
        )
        
        db.session.add(pipeline)
        db.session.commit()
        logger.info(f"Pipeline created successfully: {pipeline.pipeline_id}")
        print(f"PIPELINE_ID:{pipeline.pipeline_id}")

except Exception as e:
    logger.error(f"Failed to trigger pipeline: {e}")
    import traceback
    traceback.print_exc()
