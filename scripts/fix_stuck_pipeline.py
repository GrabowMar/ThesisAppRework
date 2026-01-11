#!/usr/bin/env python
"""Fix a stuck pipeline by adding missing job 0 and transitioning to analysis."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.factory import create_app
from app.models import PipelineExecution
from app.extensions import db

PIPELINE_ID = 'pipeline_a1f9c53e0789'

app = create_app()
with app.app_context():
    pipeline = PipelineExecution.query.filter_by(pipeline_id=PIPELINE_ID).first()
    if not pipeline:
        print(f"Pipeline {PIPELINE_ID} not found!")
        sys.exit(1)
    
    progress = pipeline.progress
    
    print("Current state:")
    print(f"  Total: {progress['generation']['total']}")
    print(f"  Completed: {progress['generation']['completed']}")
    print(f"  Failed: {progress['generation']['failed']}")
    print(f"  Results count: {len(progress['generation']['results'])}")
    print(f"  submitted_jobs: {progress['generation']['submitted_jobs']}")
    
    # Check if job 0 is missing
    job0_key = '0:anthropic_claude-3-haiku:api_url_shortener'
    if job0_key not in progress['generation']['submitted_jobs']:
        # Add job 0 as failed
        progress['generation']['results'].append({
            'job_index': 0,
            'model_slug': 'anthropic_claude-3-haiku',
            'template_slug': 'api_url_shortener',
            'app_number': None,
            'success': False,
            'error': 'Job skipped due to race condition - manually marked as failed'
        })
        progress['generation']['submitted_jobs'].append(job0_key)
        progress['generation']['failed'] += 1
        progress['generation']['status'] = 'completed'
        pipeline.progress = progress
        pipeline.current_stage = 'analysis'
        pipeline.current_job_index = 0
        db.session.commit()
        print("\nFixed! Added job 0 as failed and transitioned to analysis stage.")
    else:
        print("Job 0 already present.")
        
        # Check if we should transition to analysis
        done = progress['generation']['completed'] + progress['generation']['failed']
        total = progress['generation']['total']
        if done >= total and pipeline.current_stage == 'generation':
            progress['generation']['status'] = 'completed'
            pipeline.progress = progress
            pipeline.current_stage = 'analysis'
            pipeline.current_job_index = 0
            db.session.commit()
            print("Transitioned to analysis stage.")
