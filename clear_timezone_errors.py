#!/usr/bin/env python
"""Clear error messages from old tasks affected by timezone bug."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app.factory import create_app
from app.models import AnalysisTask
from app.extensions import db

def main():
    app = create_app()
    with app.app_context():
        # Find tasks with the timezone error
        tasks = AnalysisTask.query.filter(
            AnalysisTask.error_message.like('%offset-naive%')
        ).all()
        
        print(f"Found {len(tasks)} tasks with timezone errors")
        
        for task in tasks:
            print(f"Clearing error from {task.task_id} (status: {task.status})")
            # Clear the error message since it's just a technical issue
            task.error_message = None
            
        db.session.commit()
        print(f"✅ Cleared error messages from {len(tasks)} tasks")

if __name__ == '__main__':
    main()
