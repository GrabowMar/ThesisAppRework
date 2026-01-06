import sys
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_DIR = PROJECT_ROOT / 'src'
sys.path.insert(0, str(SRC_DIR))
os.chdir(str(PROJECT_ROOT))

from app.factory import create_app
from app.extensions import db
from app.models.pipeline import PipelineExecution, PipelineExecutionStatus

PIPELINE_ID = 'pipeline_c6b261e64ec8'

def resume_pipeline():
    app = create_app()
    with app.app_context():
        pipeline = PipelineExecution.query.filter_by(pipeline_id=PIPELINE_ID).first()
        if not pipeline:
            print(f"Pipeline {PIPELINE_ID} not found")
            return False
            
        print(f"Found pipeline: {pipeline.pipeline_id}")
        print(f"  Current status: {pipeline.status}")
        print(f"  Current stage: {pipeline.current_stage}")
        print(f"  Error: {pipeline.error_message}")
        print()
        
        # Reset pipeline to resume analysis
        pipeline.status = PipelineExecutionStatus.RUNNING
        pipeline.current_stage = 'analysis'
        pipeline.error_message = None
        
        # Reset job index to 0 so it processes all analysis jobs
        pipeline.current_job_index = 0
        
        try:
            db.session.commit()
            print("✓ Pipeline reset successfully!")
            print(f"  New status: {pipeline.status}")
            print(f"  New stage: {pipeline.current_stage}")
            print()
            print("The pipeline execution service will pick this up automatically.")
            print("Make sure the Flask app is running: python src/main.py")
            return True
        except Exception as e:
            db.session.rollback()
            print(f"✗ Failed to reset pipeline: {e}")
            return False

if __name__ == '__main__':
    resume_pipeline()
