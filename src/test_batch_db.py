#!/usr/bin/env python3
"""Test batch job database persistence."""

from app import create_app
from models import *

def test_batch_job_persistence():
    app = create_app()
    with app.app_context():
        # Get batch service
        batch_service = app.batch_service
        
        print('Testing batch job creation with database persistence...')
        
        # Create a test job
        job = batch_service.create_job(
            name='Test Security Analysis',
            description='Testing database persistence',
            analysis_types=['backend_security'],
            models=['anthropic_claude-3.7-sonnet'],
            app_range_str='1-3',
            auto_start=False
        )
        
        print(f'Created job with ID: {job.id}')
        print(f'Job status: {job.status}')
        print(f'Total tasks: {job.progress.get("total", 0)}')
        
        # Check if it was saved to database
        from models import BatchAnalysis
        db_job = BatchAnalysis.query.filter_by(id=job.id).first()
        
        if db_job:
            print('✅ Job successfully saved to database!')
            print(f'Database job name: {db_job.name}')
            print(f'Database job status: {db_job.status}')
            print(f'Database job config: {db_job.get_config()}')
        else:
            print('❌ Job NOT found in database')
        
        # List all jobs from database
        all_db_jobs = BatchAnalysis.query.all()
        print(f'Total jobs in database: {len(all_db_jobs)}')
        for db_job in all_db_jobs:
            print(f'  - {db_job.name} ({db_job.id})')

if __name__ == '__main__':
    test_batch_job_persistence()
