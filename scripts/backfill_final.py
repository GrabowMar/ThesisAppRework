"""Complete backfill using fixed result_file_writer with task_id in paths."""
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app import create_app
from app.models.analysis_models import AnalysisTask
from app.services.result_file_writer import write_task_result_files

app = create_app()

with app.app_context():
    tasks = AnalysisTask.query.filter_by(
        target_model='openai_codex-mini',
        status='completed'
    ).order_by(AnalysisTask.target_app_number, AnalysisTask.created_at).all()
    
    print(f"Found {len(tasks)} completed tasks for openai_codex-mini\n")
    print("=" * 70)
    
    success_count = 0
    error_count = 0
    
    for task in tasks:
        if not task.result_summary:
            print(f"⏭️  {task.task_id}: No result_summary")
            continue
        
        try:
            result_payload = json.loads(task.result_summary)
            
            # Call the fixed writer (now includes normalization internally)
            filepath = write_task_result_files(task, result_payload)
            
            if filepath:
                print(f"✅ {task.task_id} (app{task.target_app_number})")
                success_count += 1
            else:
                print(f"❌ {task.task_id}: Writer returned None")
                error_count += 1
            
        except Exception as e:
            print(f"❌ {task.task_id}: {str(e)[:100]}")
            error_count += 1
    
    print("=" * 70)
    print(f"\nSummary:")
    print(f"  ✅ Success: {success_count}/{len(tasks)}")
    print(f"  ❌ Errors: {error_count}/{len(tasks)}")
    print("=" * 70)
    
    if success_count == len(tasks):
        print("\n🎉 All tasks backfilled successfully!")
        print(f"\nVerify at: results/openai_codex-mini/")
    else:
        print(f"\n⚠️  {error_count} tasks failed to backfill")
