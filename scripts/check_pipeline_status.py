import sys
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent if '__file__' in dir() else Path.cwd()
PROJECT_ROOT = SCRIPT_DIR.parent if SCRIPT_DIR.name == 'scripts' else SCRIPT_DIR
SRC_DIR = PROJECT_ROOT / 'src'
sys.path.insert(0, str(SRC_DIR))
os.chdir(str(PROJECT_ROOT))

from app.factory import create_app
from app.extensions import db
from app.models.pipeline import PipelineExecution

app = create_app()
with app.app_context():
    pipeline = PipelineExecution.query.filter_by(pipeline_id='pipeline_c6b261e64ec8').first()
    if pipeline:
        print(f"Pipeline ID: {pipeline.pipeline_id}")
        print(f"Status: {pipeline.status}")
        print(f"Stage: {pipeline.current_stage}")
        print(f"Job Index: {pipeline.current_job_index}")
        print(f"Error: {pipeline.error_message}")
        print(f"Progress: {pipeline.progress}")
    else:
        print("Pipeline not found!")
