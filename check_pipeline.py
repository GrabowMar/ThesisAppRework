#!/usr/bin/env python
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import PipelineSettings, PipelineAnalysisJob
from app.extensions import db

app = create_app()
with app.app_context():
    pipeline = PipelineSettings.query.filter_by(pipeline_id='pipeline_285998fc1721').first()
    if pipeline:
        print(f"Pipeline: {pipeline.pipeline_id}")
        print(f"Status: {pipeline.status}")
        print(f"Current Stage: {pipeline.current_stage}")
        print()
        
        print("=== Generation Jobs ===")
        jobs = PipelineAnalysisJob.query.filter_by(
            pipeline_id='pipeline_285998fc1721'
        ).order_by(PipelineAnalysisJob.job_index).all()
        
        for job in jobs:
            print(f"Job {job.job_index}: {job.model_slug}/app{job.app_number}")
            print(f"  Template: {job.template_slug}")
            print(f"  Status: {job.generation_status}")
            print(f"  Error: {job.generation_error}")
            print()
    else:
        print("Pipeline not found")
