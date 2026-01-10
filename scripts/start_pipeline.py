"""Start a pending pipeline by setting its status to running."""
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
