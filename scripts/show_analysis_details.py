"""
Enhanced script to display detailed analysis results including summaries from tasks.
"""
import sys
import os
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.factory import create_app
from app.models import AnalysisTask, AnalysisResult, db
from app.constants import AnalysisStatus

def format_datetime(dt: Optional[datetime]) -> str:
    """Format datetime for display."""
    if dt is None:
        return "N/A"
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def print_json_pretty(data: Any, indent: int = 2):
    """Pretty print JSON data."""
    if isinstance(data, (dict, list)):
        print(json.dumps(data, indent=indent, default=str))
    else:
        print(data)

def display_task_with_summary(task_id: str):
    """Display task details including result_summary JSON."""
    task = AnalysisTask.query.filter_by(task_id=task_id).first()
    
    if not task:
        print(f"\nTask '{task_id}' not found.")
        return
    
    print("\n" + "="*100)
    print(f"DETAILED ANALYSIS: {task_id}")
    print("="*100)
    
    print(f"\n📋 Basic Information:")
    print(f"  Status: {task.status.value if task.status else 'UNKNOWN'}")
    print(f"  Target: {task.target_model} / App {task.target_app_number}")
    print(f"  Task Name: {task.task_name or 'N/A'}")
    print(f"  Service: {task.service_name or 'Main Task' if task.is_main_task else 'N/A'}")
    print(f"  Type: {'Main Task' if task.is_main_task else 'Subtask'}")
    
    print(f"\n⏱️  Timing:")
    print(f"  Created: {format_datetime(task.created_at)}")
    print(f"  Started: {format_datetime(task.started_at)}")
    print(f"  Completed: {format_datetime(task.completed_at)}")
    if task.actual_duration:
        print(f"  Duration: {task.actual_duration:.2f} seconds")
    
    print(f"\n📊 Progress:")
    print(f"  Progress: {task.progress_percentage:.1f}%")
    print(f"  Steps: {task.completed_steps}/{task.total_steps if task.total_steps else 'N/A'}")
    if task.current_step:
        print(f"  Current: {task.current_step}")
    
    if task.error_message:
        print(f"\n❌ Error:")
        print(f"  {task.error_message}")
    
    # Display result summary if available
    result_summary = task.get_result_summary()
    if result_summary:
        print(f"\n📦 Result Summary:")
        print_json_pretty(result_summary)
    else:
        print(f"\n📦 Result Summary: (empty)")
    
    # Display metadata if available
    metadata = task.get_metadata()
    if metadata:
        print(f"\n🏷️  Metadata:")
        print_json_pretty(metadata)
    
    # Display execution context if available
    exec_context = task.get_execution_context()
    if exec_context:
        print(f"\n⚙️  Execution Context:")
        print_json_pretty(exec_context)
    
    # Display severity breakdown if available
    severity = task.get_severity_breakdown()
    if severity:
        print(f"\n⚠️  Severity Breakdown:")
        print_json_pretty(severity)
    
    # If main task, show subtasks
    if task.is_main_task:
        subtasks = task.get_all_subtasks()
        if subtasks:
            print(f"\n📑 Subtasks ({len(subtasks)}):")
            for st in subtasks:
                status_icon = "✅" if st.status == AnalysisStatus.COMPLETED else "❌" if st.status == AnalysisStatus.FAILED else "⏳"
                duration = f"{st.actual_duration:.1f}s" if st.actual_duration else "N/A"
                print(f"  {status_icon} {st.service_name:<20} [{st.status.value:<10}] Duration: {duration}")
                
                # Show subtask summary if available
                st_summary = st.get_result_summary()
                if st_summary:
                    print(f"     Summary preview: {str(st_summary)[:100]}...")

def display_all_tasks_with_summaries():
    """Display all tasks with their summaries."""
    print("\n" + "="*100)
    print("ALL ANALYSIS TASKS WITH SUMMARIES")
    print("="*100)
    
    tasks = AnalysisTask.query.filter_by(is_main_task=True).order_by(AnalysisTask.created_at.desc()).all()
    
    if not tasks:
        print("\nNo main analysis tasks found.")
        return
    
    print(f"\nFound {len(tasks)} main tasks:\n")
    
    for i, task in enumerate(tasks, 1):
        status_icon = "✅" if task.status == AnalysisStatus.COMPLETED else "❌" if task.status == AnalysisStatus.FAILED else "⏳"
        print(f"\n{i}. {status_icon} {task.task_id}")
        print(f"   Model: {task.target_model} / App {task.target_app_number}")
        print(f"   Status: {task.status.value if task.status else 'UNKNOWN'}")
        print(f"   Created: {format_datetime(task.created_at)}")
        if task.actual_duration:
            print(f"   Duration: {task.actual_duration:.2f}s")
        
        # Show subtask count
        subtasks = task.get_all_subtasks()
        if subtasks:
            completed = sum(1 for st in subtasks if st.status == AnalysisStatus.COMPLETED)
            print(f"   Subtasks: {completed}/{len(subtasks)} completed")
        
        # Preview result summary
        result_summary = task.get_result_summary()
        if result_summary:
            summary_str = json.dumps(result_summary, default=str)
            if len(summary_str) > 100:
                summary_str = summary_str[:100] + "..."
            print(f"   Summary: {summary_str}")
        else:
            print(f"   Summary: (no data)")
        
        if task.error_message:
            error_preview = task.error_message[:80] + "..." if len(task.error_message) > 80 else task.error_message
            print(f"   ⚠️  Error: {error_preview}")

def show_quick_stats():
    """Show quick statistics about analysis tasks."""
    print("\n" + "="*100)
    print("QUICK STATISTICS")
    print("="*100)
    
    total_tasks = AnalysisTask.query.count()
    main_tasks = AnalysisTask.query.filter_by(is_main_task=True).count()
    subtasks = AnalysisTask.query.filter_by(is_main_task=False).count()
    
    completed = AnalysisTask.query.filter_by(status=AnalysisStatus.COMPLETED).count()
    failed = AnalysisTask.query.filter_by(status=AnalysisStatus.FAILED).count()
    running = AnalysisTask.query.filter_by(status=AnalysisStatus.RUNNING).count()
    pending = AnalysisTask.query.filter_by(status=AnalysisStatus.PENDING).count()
    
    print(f"\n📊 Task Counts:")
    print(f"  Total Tasks: {total_tasks}")
    print(f"  Main Tasks: {main_tasks}")
    print(f"  Subtasks: {subtasks}")
    
    print(f"\n📈 Status Breakdown:")
    print(f"  ✅ Completed: {completed}")
    print(f"  ❌ Failed: {failed}")
    print(f"  ⏳ Running: {running}")
    print(f"  📋 Pending: {pending}")
    
    # Get models analyzed
    models = db.session.query(AnalysisTask.target_model).distinct().all()
    print(f"\n🤖 Models Analyzed: {len(models)}")
    for model_tuple in models:
        model = model_tuple[0]
        count = AnalysisTask.query.filter_by(target_model=model, is_main_task=True).count()
        print(f"  - {model}: {count} analysis runs")
    
    # Check for results in AnalysisResult table
    result_count = AnalysisResult.query.count()
    print(f"\n📝 Detailed Results Stored: {result_count}")

def main():
    """Main entry point."""
    app = create_app()
    
    with app.app_context():
        if len(sys.argv) > 1:
            command = sys.argv[1]
            
            if command == "stats":
                show_quick_stats()
            elif command == "list":
                display_all_tasks_with_summaries()
            elif command == "task" and len(sys.argv) > 2:
                task_id = sys.argv[2]
                display_task_with_summary(task_id)
            elif command == "latest":
                # Show latest main task
                task = AnalysisTask.query.filter_by(is_main_task=True).order_by(AnalysisTask.created_at.desc()).first()
                if task:
                    display_task_with_summary(task.task_id)
                else:
                    print("No tasks found.")
            else:
                print("Usage:")
                print("  python show_analysis_details.py stats              - Show quick statistics")
                print("  python show_analysis_details.py list               - List all main tasks")
                print("  python show_analysis_details.py task <task_id>     - Show detailed task info")
                print("  python show_analysis_details.py latest             - Show latest task")
        else:
            # Default: show stats and list
            show_quick_stats()
            display_all_tasks_with_summaries()

if __name__ == "__main__":
    main()
