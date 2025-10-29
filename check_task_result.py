#!/usr/bin/env python3
"""Check task result storage."""
import sys
sys.path.insert(0, 'src')

from app import create_app
from app.models import AnalysisTask

app = create_app()
with app.app_context():
    task = AnalysisTask.query.filter_by(task_id='task_c0e7bdb31730').first()
    print(f'Task found: {task is not None}')
    if task:
        print(f'Status: {task.status}')
        print(f'Has result_summary: {task.result_summary is not None}')
        if task.result_summary:
            print(f'result_summary type: {type(task.result_summary)}')
            print(f'result_summary length: {len(task.result_summary)}')
            print(f'First 500 chars: {str(task.result_summary)[:500]}')
            # Try to parse it
            try:
                data = task.get_result_summary()
                print(f'Parsed successfully: {data is not None}')
                if data:
                    print(f'Keys in data: {list(data.keys())}')
                    if 'summary' in data:
                        print(f'Summary keys: {list(data["summary"].keys())}')
            except Exception as e:
                print(f'Failed to parse: {e}')
        else:
            print('result_summary is None or empty')
