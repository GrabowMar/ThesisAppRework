import sys
import os
import json

# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from app.factory import create_app
from app.models import PipelineExecution

def check_pipeline():
    app = create_app()
    with app.app_context():
        pipeline = PipelineExecution.query.order_by(PipelineExecution.created_at.desc()).first()
        if not pipeline:
            print("No pipelines found.")
            return

        print(f"Pipeline: {pipeline.name}")
        print(f"ID: {pipeline.pipeline_id}")
        print(f"Status: {pipeline.status}")
        print(f"Stage: {pipeline.current_stage}")
        print(f"Job Index: {pipeline.current_job_index}")
        
        config = pipeline.config
        gen_config = config.get('generation', {})
        models = gen_config.get('models', [])
        print(f"Models ({len(models)}): {', '.join(models)}")
        print(f"Templates ({len(gen_config.get('templates', []))})")
        
        progress = pipeline.progress
        gen_progress = progress.get('generation', {})
        print(f"Generation Progress: {gen_progress.get('completed')}/{gen_progress.get('total')} ({gen_progress.get('failed')} failed)")
        
        analysis_progress = progress.get('analysis', {})
        print(f"Analysis Progress: {analysis_progress.get('completed')}/{analysis_progress.get('total')} ({analysis_progress.get('failed')} failed)")
        
        print(f"Overall Progress: {pipeline.get_overall_progress()}%")

if __name__ == "__main__":
    check_pipeline()
