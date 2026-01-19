"""
Start Pending Pipeline Execution
================================

This script manually starts a pending pipeline by changing its status to RUNNING.

The script is used for pipeline management and debugging. It allows administrators
to manually trigger pipeline execution when automatic scheduling is not desired.

Usage:
    python scripts/start_pipeline.py <pipeline_id>

Arguments:
    pipeline_id: The unique identifier of the pipeline to start

The script will:
1. Look up the pipeline by ID
2. Display current pipeline status and configuration
3. Change status from PENDING to RUNNING if applicable
4. Commit the status change to the database

Note: This script should only be used for debugging or manual pipeline management.
Normal pipeline execution should be handled by the automated pipeline scheduler.
"""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import PipelineExecution, PipelineExecutionStatus
from app.extensions import db

# Get pipeline_id from argument
pipeline_id = sys.argv[1] if len(sys.argv) > 1 else None

if not pipeline_id:
    print("Usage: python start_pipeline.py <pipeline_id>")
    sys.exit(1)

app = create_app()
with app.app_context():
    pipeline = PipelineExecution.query.filter_by(pipeline_id=pipeline_id).first()
    
    if not pipeline:
        print(f"Pipeline {pipeline_id} not found")
        sys.exit(1)
    
    print(f"Pipeline: {pipeline.pipeline_id}")
    print(f"Current status: {pipeline.status}")
    print(f"Stage: {pipeline.current_stage}")
    print(f"Config: {pipeline.config}")
    print()
    
    if pipeline.status == PipelineExecutionStatus.PENDING:
        # Start the pipeline
        pipeline.status = PipelineExecutionStatus.RUNNING
        db.session.commit()
        print(f"✓ Pipeline status changed to: {pipeline.status.value}")
    else:
        print(f"Pipeline is already in status: {pipeline.status.value}")
