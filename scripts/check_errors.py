"""
Check Analysis Task Errors
==========================

This script queries and displays recent failed analysis tasks from the database.

The script shows the most recent failed tasks (up to 10) with details including:
- Task ID and status
- Target model and application number
- Parent task relationship
- Error messages
- Creation timestamps

Usage:
    python scripts/check_errors.py

This is useful for debugging pipeline failures and monitoring system health.
Tasks are ordered by creation date (most recent first).
"""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import AnalysisTask

app = create_app()
with app.app_context():
    # Get failed tasks from recent pipeline
    tasks = AnalysisTask.query.filter(
        AnalysisTask.status.in_(['failed', 'FAILED'])
    ).order_by(AnalysisTask.created_at.desc()).limit(10).all()
    
    for t in tasks:
        print(f"\nTask: {t.task_id}")
        print(f"  Model: {t.target_model}")
        print(f"  App: {t.target_app_number}")
        print(f"  Status: {t.status}")
        print(f"  Parent: {t.parent_task_id}")
        print(f"  Error: {t.error_message}")
        print(f"  Created: {t.created_at}")
