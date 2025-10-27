"""
Database-based Parallel Execution Verification
Analyzes existing tasks to verify parallel vs sequential execution
"""
import sqlite3
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
DB_PATH = project_root / 'src' / 'data' / 'thesis_app.db'

def analyze_existing_tasks():
    """Analyze recent tasks to check execution patterns"""
    print("\n" + "="*80)
    print("  ANALYZING EXISTING TASKS FOR PARALLEL EXECUTION")
    print("="*80 + "\n")
    
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    
    # Get recent main tasks
    recent_tasks = cur.execute("""
        SELECT task_id, target_model, target_app_number, status, 
               created_at, started_at, completed_at
        FROM analysis_tasks
        WHERE is_main_task=1
        ORDER BY created_at DESC
        LIMIT 10
    """).fetchall()
    
    print(f"Found {len(recent_tasks)} recent main tasks:\n")
    
    for task_id, model, app, status, created, started, completed in recent_tasks:
        print(f"Task: {task_id[:20]}...")
        print(f"  Model: {model}, App: {app}")
        print(f"  Status: {status}")
        print(f"  Created: {created}")
        
        # Get subtasks
        subtasks = cur.execute("""
            SELECT service_name, status, created_at, started_at, completed_at
            FROM analysis_tasks
            WHERE parent_task_id=?
            ORDER BY service_name
        """, (task_id,)).fetchall()
        
        if subtasks:
            print(f"  Subtasks: {len(subtasks)}")
            
            # Analyze timing to detect parallel execution
            start_times = [s[3] for s in subtasks if s[3]]  # started_at
            
            if start_times and len(start_times) > 1:
                # Parse timestamps
                timestamps = [datetime.fromisoformat(t.replace('Z', '+00:00')) if isinstance(t, str) else t 
                             for t in start_times]
                
                # Check if multiple tasks started within 5 seconds of each other
                if len(timestamps) > 1:
                    earliest = min(timestamps)
                    latest = max(timestamps)
                    time_spread = (latest - earliest).total_seconds()
                    
                    if time_spread < 5:
                        print(f"  🚀 PARALLEL EXECUTION DETECTED! ({len(timestamps)} tasks started within {time_spread:.1f}s)")
                    else:
                        print(f"  ⚠️  Sequential execution (tasks spread over {time_spread:.1f}s)")
            
            # Show subtask details
            for svc, st_status, st_created, st_started, st_completed in subtasks:
                print(f"    - {svc:20s}: {st_status}")
        
        print()
    
    conn.close()
    
    # Check logs for parallel execution indicators
    print("\n" + "="*80)
    print("  CHECKING LOGS FOR PARALLEL EXECUTION")
    print("="*80 + "\n")
    
    log_file = project_root / 'logs' / 'app.log'
    
    if log_file.exists():
        with open(log_file) as f:
            lines = f.readlines()
        
        # Look for parallel execution indicators
        chord_lines = [line for line in lines if 'Celery chord created' in line]
        sequential_lines = [line for line in lines if 'Executing subtasks SEQUENTIALLY' in line or 'Executing subtasks sequentially' in line]
        
        print(f"Celery chord creations: {len(chord_lines)}")
        print(f"Sequential fallback uses: {len(sequential_lines)}\n")
        
        if chord_lines:
            print("Recent Celery chord creations:")
            for line in chord_lines[-5:]:
                print(f"  {line.strip()}")
        
        if sequential_lines:
            print("\nRecent sequential fallback uses:")
            for line in sequential_lines[-5:]:
                print(f"  {line.strip()}")
        
        # Check for our new pre-flight check errors
        preflight_errors = [line for line in lines if 'Celery workers not available' in line]
        if preflight_errors:
            print(f"\n⚠️  Pre-flight check failures: {len(preflight_errors)}")
            for line in preflight_errors[-3:]:
                print(f"  {line.strip()}")
    else:
        print("❌ Log file not found")
    
    # Final summary
    print("\n" + "="*80)
    print("  SUMMARY")
    print("="*80 + "\n")
    
    if chord_lines and len(chord_lines) > len(sequential_lines):
        print("✅ System is using parallel Celery chord execution (NEW CODE)")
    elif sequential_lines and len(sequential_lines) > len(chord_lines):
        print("⚠️  System is still using sequential fallback (OLD CODE)")
        print("   Flask server needs to be restarted to load new code!")
    else:
        print("ℹ️  Insufficient data to determine execution mode")
    
    if preflight_errors:
        print(f"\n⚠️  {len(preflight_errors)} tasks failed due to Celery workers not running")
        print("   This is EXPECTED behavior with the new parallel-only code")

if __name__ == '__main__':
    analyze_existing_tasks()
