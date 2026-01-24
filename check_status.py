import os
import sys
import json
from app import create_app
from app.models.pipeline import PipelineExecution

sys.path.insert(0, "/app/src")
sys.path.insert(0, "/app")

os.environ["FLASK_ENV"] = "development"

app = create_app()

with app.app_context():
    # Find latest pipeline
    pipeline = PipelineExecution.query.order_by(PipelineExecution.created_at.desc()).first()
    
    if pipeline:
        print(f"Pipeline ID: {pipeline.pipeline_id}")
        print(f"Status: {pipeline.status}")
        print(f"Stage: {pipeline.current_stage}")
        print("-" * 50)
        print("Progress:")
        # Pretty print JSON
        print(json.dumps(pipeline.progress, indent=2))
        print("-" * 50)
        
        if pipeline.error_message:
            print(f"Error: {pipeline.error_message}")
            
    else:
        print("No pipelines found.")
