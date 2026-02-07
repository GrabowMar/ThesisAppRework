import sys
import os
sys.path.insert(0, os.getcwd())
# Ensure src is in path for imports
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

from src.app.factory import create_app
from src.app.extensions import db

# Create the app instance
app = create_app()

# Use app context for DB operations
with app.app_context():
    # Import models inside context to avoid registry errors
    from src.app.models.pipeline import PipelineExecution, PipelineExecutionStatus
    
    print("Finding running pipelines...")
    # Find running pipelines and mark them as failed/cancelled
    running_pipelines = PipelineExecution.query.filter(
        PipelineExecution.status.in_([PipelineExecutionStatus.RUNNING, PipelineExecutionStatus.PENDING])
    ).all()
    
    count = 0
    for p in running_pipelines:
        p.status = PipelineExecutionStatus.FAILED
        p.error_message = "Manually cancelled by user (cleanup)"
        count += 1
    
    if count > 0:
        db.session.commit()
        print(f"Reset {count} stuck pipelines.")
    else:
        print("No stuck pipelines found.")
