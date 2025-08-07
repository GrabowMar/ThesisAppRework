#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from models import BatchJob, JobStatus, JobPriority
from extensions import db
import json
from datetime import datetime
import uuid

# Initialize Flask app
from flask import Flask
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data/thesis_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    # Create sample test jobs
    job1 = BatchJob(
        id=str(uuid.uuid4()),
        name='Sample Security Scan',
        description='Demonstration security analysis job',
        status=JobStatus.PENDING,
        priority=JobPriority.NORMAL,
        total_tasks=100,
        completed_tasks=0,
        failed_tasks=0,
        analysis_types_json=json.dumps(['security', 'bandit']),
        models_json=json.dumps(['anthropic/claude-3-haiku']),
        app_range_json=json.dumps({'start': 1, 'end': 5}),
        estimated_duration_minutes=30
    )
    db.session.add(job1)
    
    # Create another job that is running
    job2 = BatchJob(
        id=str(uuid.uuid4()),
        name='Performance Test Run',
        description='Load testing demonstration',
        status=JobStatus.RUNNING,
        priority=JobPriority.HIGH,
        total_tasks=50,
        completed_tasks=25,
        failed_tasks=2,
        analysis_types_json=json.dumps(['performance']),
        models_json=json.dumps(['openai/gpt-4']),
        started_at=datetime.utcnow(),
        estimated_duration_minutes=15
    )
    db.session.add(job2)
    
    # Create a completed job
    results = {'vulnerabilities_found': 3, 'high_risk': 1, 'medium_risk': 2}
    artifacts = [{'name': 'security_report.pdf', 'url': '/reports/security_001.pdf'}]
    
    job3 = BatchJob(
        id=str(uuid.uuid4()),
        name='ZAP Security Scan',
        description='Completed vulnerability scan',
        status=JobStatus.COMPLETED,
        priority=JobPriority.NORMAL,
        total_tasks=75,
        completed_tasks=73,
        failed_tasks=2,
        analysis_types_json=json.dumps(['zap', 'security']),
        models_json=json.dumps(['openai/gpt-3.5-turbo']),
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
        actual_duration_seconds=1800,
        results_summary_json=json.dumps(results),
        artifacts_json=json.dumps(artifacts)
    )
    db.session.add(job3)
    
    db.session.commit()
    print('Sample test jobs created successfully!')
    print(f'Job 1 (Pending): {job1.id}')
    print(f'Job 2 (Running): {job2.id}')
    print(f'Job 3 (Completed): {job3.id}')
