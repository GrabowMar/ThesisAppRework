#!/usr/bin/env python3
"""Test batch job with successful mock execution."""

from app import create_app
from models import *
import time

def test_batch_job_success():
    app = create_app()
    with app.app_context():
        batch_service = app.batch_service
        
        print('Testing successful batch job execution...')
        
        # Create a test job with performance analysis which should have mock data
        job = batch_service.create_job(
            name='Performance Test Job',
            description='Testing successful job execution with mock data',
            analysis_types=['performance'],
            models=['anthropic_claude-3.7-sonnet'],
            app_range_str='1-2',
            auto_start=True
        )
        
        print(f'Created and started job: {job.id}')
        print(f'Total tasks: {job.progress.get("total", 0)}')
        
        # Monitor progress
        for i in range(15):
            current_job = batch_service.get_job(job.id)
            if current_job:
                completed = current_job.progress.get("completed", 0)
                total = current_job.progress.get("total", 0)
                failed = current_job.progress.get("failed", 0)
                
                print(f'Progress: {completed}/{total} (failed: {failed}) - Status: {current_job.status}')
                
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
            print(f'  - Progress: {db_job.get_progress_percentage()}%')
            print(f'  - Duration: {(db_job.completed_at - db_job.started_at).total_seconds():.2f}s')
            
            if db_job.status.value == 'completed':
                print('🎉 Job completed successfully!')
            else:
                print(f'⚠️  Job ended with status: {db_job.status}')
        else:
            print('❌ Job not found in database')

if __name__ == '__main__':
    test_batch_job_success()
