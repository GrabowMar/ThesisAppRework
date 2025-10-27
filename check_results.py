#!/usr/bin/env python
"""Check if analysis results are being saved and are viewable."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app.factory import create_app
from app.models import AnalysisTask
from app.extensions import db

def main():
    app = create_app()
    with app.app_context():
        # Get completed tasks
        tasks = AnalysisTask.query.filter(
            AnalysisTask.status.in_(['completed', 'failed']),
            AnalysisTask.target_model == 'anthropic_claude-4.5-haiku-20251001'
        ).order_by(AnalysisTask.created_at.desc()).limit(3).all()
        
        print(f"Found {len(tasks)} recent tasks\n")
        
        for task in tasks:
            print(f"Task: {task.task_id}")
            print(f"  Status: {task.status}")
            print(f"  Type: {task.analysis_type}")
            print(f"  Is Main: {task.is_main_task}")
            print(f"  Subtasks: {len(task.subtasks) if task.subtasks else 0}")
            
            # Check for results
            try:
                metadata = task.get_metadata()
                if metadata:
                    # Check for analysis results
                    if 'analysis' in metadata or 'summary' in metadata:
                        print(f"  ✅ Has analysis results in metadata")
                        if 'summary' in metadata:
                            summary = metadata['summary']
                            if isinstance(summary, dict):
                                print(f"     Total findings: {summary.get('total_findings', 0)}")
                                print(f"     Tools executed: {summary.get('tools_executed', 0)}")
                    else:
                        print(f"  ⚠️  No analysis results in metadata")
                else:
                    print(f"  ⚠️  No metadata")
            except Exception as e:
                print(f"  ❌ Error reading metadata: {e}")
            
            # Check result summary
            try:
                result_summary = task.get_result_summary()
                if result_summary and isinstance(result_summary, dict):
                    print(f"  ✅ Has result summary")
                    if 'tools' in result_summary:
                        print(f"     Tools count: {len(result_summary.get('tools', {}))}")
                    if 'services' in result_summary:
                        print(f"     Services count: {len(result_summary.get('services', {}))}")
                else:
                    print(f"  ⚠️  No result summary")
            except Exception as e:
                print(f"  ❌ Error reading result summary: {e}")
            
            print()

if __name__ == '__main__':
    main()
