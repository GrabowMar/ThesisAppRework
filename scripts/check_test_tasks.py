#!/usr/bin/env python3
"""Check status of specific analysis tasks"""
import sys
sys.path.insert(0, 'src')

from app import create_app
from app.models import AnalysisTask

app = create_app()

task_ids = ['task_7ec2bff376c0', 'task_29eb8f6bb3f3', 'task_9250a69f3c03']

with app.app_context():
    tasks = AnalysisTask.query.filter(AnalysisTask.task_id.in_(task_ids)).all()
    
    print("\nTask Status:")
    print("=" * 80)
    for t in tasks:
        duration = (t.updated_at - t.created_at).total_seconds() / 60 if t.updated_at else 0
        print(f"{t.task_id}: {t.status.value.upper().ljust(12)} "
              f"| Type: {t.analysis_type.ljust(30)} "
              f"| Duration: {duration:.1f}min")
    print("=" * 80)
    print()
