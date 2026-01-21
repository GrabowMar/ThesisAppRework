#!/usr/bin/env python3
"""Monitor analysis tasks in real-time."""
import sys
import time
from datetime import datetime

sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import AnalysisTask
from app.constants import AnalysisStatus

app = create_app()

def get_task_counts():
    with app.app_context():
        return {
            'pending': AnalysisTask.query.filter_by(is_main_task=True, status=AnalysisStatus.PENDING).count(),
            'created': AnalysisTask.query.filter_by(is_main_task=True, status=AnalysisStatus.CREATED).count(),
            'running': AnalysisTask.query.filter_by(is_main_task=True, status=AnalysisStatus.RUNNING).count(),
            'completed': AnalysisTask.query.filter_by(is_main_task=True, status=AnalysisStatus.COMPLETED).count(),
            'failed': AnalysisTask.query.filter_by(is_main_task=True, status=AnalysisStatus.FAILED).count(),
            'partial': AnalysisTask.query.filter_by(is_main_task=True, status=AnalysisStatus.PARTIAL_SUCCESS).count(),
        }

def get_running_tasks():
    with app.app_context():
        return AnalysisTask.query.filter_by(is_main_task=True, status=AnalysisStatus.RUNNING).all()

def get_recent_completed():
    with app.app_context():
        return AnalysisTask.query.filter_by(
            is_main_task=True, 
            status=AnalysisStatus.COMPLETED
        ).order_by(AnalysisTask.updated_at.desc()).limit(3).all()

def main():
    print("=" * 80)
    print("MONITORING ANALYSIS TASKS")
    print("=" * 80)
    print("\nPress Ctrl+C to stop\n")
    
    iteration = 0
    prev_counts = None
    
    try:
        while True:
            iteration += 1
            now = datetime.now().strftime("%H:%M:%S")
            
            counts = get_task_counts()
            running_tasks = get_running_tasks()
            
            # Clear screen every 10 iterations
            if iteration % 10 == 1:
                print("\n" + "=" * 80)
                print(f"Status Update - {now}")
                print("=" * 80)
            
            # Show counts
            print(f"\n[{now}] ", end="")
            print(f"PENDING: {counts['pending']} | ", end="")
            print(f"RUNNING: {counts['running']} | ", end="")
            print(f"COMPLETED: {counts['completed']} | ", end="")
            print(f"FAILED: {counts['failed']} | ", end="")
            print(f"PARTIAL: {counts['partial']}")
            
            # Show what's running
            if running_tasks:
                for task in running_tasks:
                    progress = task.progress_percentage or 0
                    print(f"  ▶ {task.target_model}/app{task.target_app_number} - {progress:.0f}% - {task.current_step or 'Processing...'}")
            
            # Show changes
            if prev_counts:
                changes = []
                if counts['completed'] > prev_counts['completed']:
                    diff = counts['completed'] - prev_counts['completed']
                    changes.append(f"✅ {diff} completed")
                if counts['failed'] > prev_counts['failed']:
                    diff = counts['failed'] - prev_counts['failed']
                    changes.append(f"❌ {diff} failed")
                if counts['running'] != prev_counts['running']:
                    changes.append(f"🔄 Running changed: {prev_counts['running']} → {counts['running']}")
                
                if changes:
                    print(f"  📊 {', '.join(changes)}")
            
            prev_counts = counts
            
            # Check if all done
            total_new = 36  # From the rerun script
            total_done = counts['completed'] + counts['failed'] + counts['partial']
            if total_done >= total_new and counts['running'] == 0 and counts['pending'] == 0:
                print("\n" + "=" * 80)
                print("✅ ALL TASKS COMPLETED!")
                print("=" * 80)
                
                recent = get_recent_completed()
                if recent:
                    print("\nRecent completions:")
                    for task in recent:
                        print(f"  {task.target_model}/app{task.target_app_number} - {task.issues_found} issues")
                break
            
            time.sleep(5)  # Check every 5 seconds
            
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user")
        print("=" * 80)
        print("Final Status:")
        print("=" * 80)
        counts = get_task_counts()
        for status, count in counts.items():
            print(f"  {status.upper()}: {count}")

if __name__ == '__main__':
    main()
