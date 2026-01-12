#!/usr/bin/env python
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models.pipeline import PipelineExecution
from app.extensions import db

app = create_app()
with app.app_context():
    pipeline = PipelineExecution.query.filter_by(pipeline_id='pipeline_285998fc1721').first()
    if pipeline:
        print(f"Pipeline: {pipeline.pipeline_id}")
        print(f"Status: {pipeline.status}")
        print(f"Current Stage: {pipeline.current_stage}")
        print(f"Current Job Index: {pipeline.current_job_index}")
        print()
        
        progress = pipeline.progress
        gen = progress.get('generation', {})
        print("=== Generation Progress ===")
        print(f"Total: {gen.get('total')}")
        print(f"Completed: {gen.get('completed')}")
        print(f"Failed: {gen.get('failed')}")
        print(f"Status: {gen.get('status')}")
        print(f"In Flight: {gen.get('in_flight')}")
        print()
        
        print("=== Generation Results ===")
        for idx, result in enumerate(gen.get('results', [])):
            print(f"\nJob {idx}:")
            print(f"  Model: {result.get('model_slug')}")
            print(f"  Template: {result.get('template_slug')}")
            print(f"  App Number: {result.get('app_number')}")
            print(f"  Success: {result.get('success')}")
            print(f"  Error: {result.get('error')}")
    else:
        print("Pipeline not found")
