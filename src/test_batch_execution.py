#!/usr/bin/env python3
"""Test batch job execution and progress tracking."""

from app import create_app
from models import *
import time

def test_batch_job_execution():
    app = create_app()
    with app.app_context():
        batch_service = app.batch_service
        
        print('Testing batch job execution and progress tracking...')
        
        # Create a small test job
        job = batch_service.create_job(
            name='Execution Test Job',
            description='Testing job execution and progress tracking',
            analysis_types=['backend_security'],
            models=['anthropic_claude-3.7-sonnet'],
            app_range_str='1-2',  # Just 2 apps to make it quick
            auto_start=True  # Start automatically
        )
        
        print(f'Created and started job: {job.id}')
        print(f'Total tasks: {job.progress.get("total", 0)}')
        
        # Monitor progress for a few seconds
        for i in range(10):
            # Refresh job from memory
            current_job = batch_service.get_job(job.id)
            if current_job:
                print(f'Progress: {current_job.progress.get("completed", 0)}/{current_job.progress.get("total", 0)} - Status: {current_job.status}')
                
                if current_job.status.value in ['completed', 'failed']:
                    break
                    
            time.sleep(1)
        
        # Check final database state
        from models import BatchAnalysis
        db_job = BatchAnalysis.query.filter_by(id=job.id).first()
        
        if db_job:
            print(f'✅ Final database state:')
            print(f'  - Status: {db_job.status}')
            print(f'  - Completed: {db_job.completed_applications}')
            print(f'  - Failed: {db_job.failed_applications}')
            print(f'  - Started at: {db_job.started_at}')
            print(f'  - Completed at: {db_job.completed_at}')
        else:
            print('❌ Job not found in database')

if __name__ == '__main__':
    test_batch_job_execution()
