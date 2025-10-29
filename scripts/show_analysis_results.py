"""
Script to display analysis results from the database.
"""
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.factory import create_app
from app.models import AnalysisTask, AnalysisResult, db
from app.constants import AnalysisStatus, SeverityLevel

def format_datetime(dt: Optional[datetime]) -> str:
    """Format datetime for display."""
    if dt is None:
        return "N/A"
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def display_tasks_summary():
    """Display summary of all analysis tasks."""
    print("\n" + "="*100)
    print("ANALYSIS TASKS SUMMARY")
    print("="*100)
    
    tasks = AnalysisTask.query.order_by(AnalysisTask.created_at.desc()).all()
    
    if not tasks:
        print("No analysis tasks found in database.")
        return
    
    print(f"\nTotal tasks: {len(tasks)}\n")
    
    # Group by status
    status_counts = {}
    for task in tasks:
        status = task.status.value if task.status else "UNKNOWN"
        status_counts[status] = status_counts.get(status, 0) + 1
    
    print("Status breakdown:")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}")
    
    print("\n" + "-"*100)
    print(f"{'Task ID':<40} {'Status':<15} {'Model':<30} {'App':<5} {'Created'}")
    print("-"*100)
    
    for task in tasks[:20]:  # Show last 20 tasks
        status = task.status.value if task.status else "UNKNOWN"
        created = format_datetime(task.created_at)
        print(f"{task.task_id:<40} {status:<15} {task.target_model:<30} {task.target_app_number:<5} {created}")

def display_task_details(task_id: str):
    """Display detailed information about a specific task."""
    task = AnalysisTask.query.filter_by(task_id=task_id).first()
    
    if not task:
        print(f"\nTask '{task_id}' not found.")
        return
    
    print("\n" + "="*100)
    print(f"TASK DETAILS: {task_id}")
    print("="*100)
    
    print(f"\nBasic Information:")
    print(f"  Status: {task.status.value if task.status else 'UNKNOWN'}")
    print(f"  Target Model: {task.target_model}")
    print(f"  Target App: {task.target_app_number}")
    print(f"  Task Name: {task.task_name or 'N/A'}")
    print(f"  Is Main Task: {task.is_main_task}")
    print(f"  Service Name: {task.service_name or 'N/A'}")
    print(f"  Parent Task: {task.parent_task_id or 'N/A'}")
    
    print(f"\nProgress:")
    print(f"  Progress: {task.progress_percentage:.1f}%")
    print(f"  Current Step: {task.current_step or 'N/A'}")
    print(f"  Completed Steps: {task.completed_steps}/{task.total_steps if task.total_steps else 'N/A'}")
    
    print(f"\nTiming:")
    print(f"  Created: {format_datetime(task.created_at)}")
    print(f"  Started: {format_datetime(task.started_at)}")
    print(f"  Completed: {format_datetime(task.completed_at)}")
    if task.actual_duration:
        print(f"  Duration: {task.actual_duration:.2f} seconds")
    
    print(f"\nResults:")
    print(f"  Issues Found: {task.issues_found}")
    if task.error_message:
        print(f"  Error: {task.error_message}")
    
    # Display subtasks if main task
    if task.is_main_task:
        subtasks = task.get_all_subtasks()
        if subtasks:
            print(f"\nSubtasks ({len(subtasks)}):")
            for subtask in subtasks:
                status = subtask.status.value if subtask.status else 'UNKNOWN'
                print(f"  - {subtask.task_id} [{status}] {subtask.service_name}")
    
    # Display results
    results = AnalysisResult.query.filter_by(task_id=task_id).all()
    if results:
        display_results_for_task(task_id, results)
    else:
        print(f"\nNo detailed results found for this task.")

def display_results_for_task(task_id: str, results=None):
    """Display analysis results for a specific task."""
    if results is None:
        results = AnalysisResult.query.filter_by(task_id=task_id).all()
    
    if not results:
        print(f"\nNo results found for task '{task_id}'")
        return
    
    print(f"\n" + "="*100)
    print(f"ANALYSIS RESULTS FOR TASK: {task_id}")
    print(f"="*100)
    print(f"\nTotal findings: {len(results)}\n")
    
    # Group by severity
    severity_counts = {}
    for result in results:
        severity = result.severity.value if result.severity else "UNKNOWN"
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
    
    print("Severity breakdown:")
    for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']:
        count = severity_counts.get(severity, 0)
        if count > 0:
            print(f"  {severity}: {count}")
    
    # Group by tool
    tool_counts = {}
    for result in results:
        tool_counts[result.tool_name] = tool_counts.get(result.tool_name, 0) + 1
    
    print("\nTools breakdown:")
    for tool, count in sorted(tool_counts.items()):
        print(f"  {tool}: {count}")
    
    print("\n" + "-"*100)
    print(f"{'Tool':<20} {'Severity':<12} {'Category':<20} {'Title':<48}")
    print("-"*100)
    
    for result in results:
        severity = result.severity.value if result.severity else "UNKNOWN"
        title = result.title[:45] + "..." if len(result.title) > 48 else result.title
        print(f"{result.tool_name:<20} {severity:<12} {result.category or 'N/A':<20} {title:<48}")

def display_all_results():
    """Display summary of all results in database."""
    print("\n" + "="*100)
    print("ALL ANALYSIS RESULTS SUMMARY")
    print("="*100)
    
    results = AnalysisResult.query.all()
    
    if not results:
        print("\nNo analysis results found in database.")
        return
    
    print(f"\nTotal findings: {len(results)}\n")
    
    # Group by task
    task_results = {}
    for result in results:
        if result.task_id not in task_results:
            task_results[result.task_id] = []
        task_results[result.task_id].append(result)
    
    print(f"Results across {len(task_results)} tasks:\n")
    
    for task_id, task_results_list in task_results.items():
        task = AnalysisTask.query.filter_by(task_id=task_id).first()
        model = task.target_model if task else "Unknown"
        app_num = task.target_app_number if task else "?"
        
        severity_counts = {}
        for result in task_results_list:
            severity = result.severity.value if result.severity else "UNKNOWN"
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        severity_str = ", ".join([f"{sev}: {count}" for sev, count in sorted(severity_counts.items())])
        print(f"  {task_id[:40]:<42} [{model}/{app_num}] - {len(task_results_list)} findings ({severity_str})")

def main():
    """Main entry point."""
    app = create_app()
    
    with app.app_context():
        if len(sys.argv) > 1:
            command = sys.argv[1]
            
            if command == "tasks":
                display_tasks_summary()
            elif command == "task" and len(sys.argv) > 2:
                task_id = sys.argv[2]
                display_task_details(task_id)
            elif command == "results":
                if len(sys.argv) > 2:
                    task_id = sys.argv[2]
                    display_results_for_task(task_id)
                else:
                    display_all_results()
            else:
                print("Unknown command. Usage:")
                print("  python show_analysis_results.py tasks              - Show all tasks")
                print("  python show_analysis_results.py task <task_id>     - Show task details")
                print("  python show_analysis_results.py results            - Show all results")
                print("  python show_analysis_results.py results <task_id>  - Show results for task")
        else:
            # Default: show both tasks and results
            display_tasks_summary()
            print("\n")
            display_all_results()

if __name__ == "__main__":
    main()
