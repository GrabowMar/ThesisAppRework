"""Backfill result files for tasks that only have database entries."""
import sys
import json
from pathlib import Path
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import AnalysisTask
from datetime import datetime

app = create_app()

def write_result_file(task: AnalysisTask, result_summary: dict):
    """Write result file to disk in the expected format."""
    # Get project root
    project_root = Path(__file__).parent
    
    # Create results directory structure
    model_safe = task.target_model.replace('/', '_').replace('\\', '_')
    results_dir = project_root / 'results' / model_safe / f'app{task.target_app_number}'
    
    # Create task-specific directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    task_dir = results_dir / f'task_{task.analysis_type}_{timestamp}'
    task_dir.mkdir(parents=True, exist_ok=True)
    
    # Write main result file
    filename = f'{model_safe}_app{task.target_app_number}_task_{task.analysis_type}_{timestamp}_{timestamp}.json'
    filepath = task_dir / filename
    
    # Wrap in standard format with metadata
    wrapped_payload = {
        'task_id': task.task_id,
        'model_slug': task.target_model,
        'app_number': task.target_app_number,
        'analysis_type': task.analysis_type.value if hasattr(task.analysis_type, 'value') else str(task.analysis_type),
        'timestamp': datetime.now().isoformat() + '+00:00',
        'metadata': {
            'task_id': task.task_id,
            'model_slug': task.target_model,
            'app_number': task.target_app_number,
            'analysis_type': task.analysis_type.value if hasattr(task.analysis_type, 'value') else str(task.analysis_type),
            'timestamp': datetime.now().isoformat() + '+00:00',
            'analyzer_version': '1.0.0',
            'module': task.analysis_type.value if hasattr(task.analysis_type, 'value') else str(task.analysis_type),
            'version': '1.0'
        },
        'results': result_summary.get('payload', result_summary),
        'summary': result_summary.get('payload', {}).get('summary', {}),
    }
    
    # Write file
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(wrapped_payload, f, indent=2, default=str)
    
    print(f"✅ Created: {filepath}")
    
    # Write manifest
    manifest_path = task_dir / 'manifest.json'
    manifest = {
        'task_id': task.task_id,
        'model_slug': task.target_model,
        'app_number': task.target_app_number,
        'primary_result': filename,
        'services': [],
        'service_files': {},
        'created_at': datetime.now().isoformat() + '+00:00'
    }
    
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"✅ Created: {manifest_path}")
    
    return filepath

with app.app_context():
    # Find completed tasks that have database results but no disk files
    tasks = AnalysisTask.query.filter_by(
        target_model='anthropic_claude-4.5-haiku-20251001',
        target_app_number=1,
        status='completed'
    ).order_by(AnalysisTask.created_at.desc()).all()
    
    print(f"Found {len(tasks)} completed tasks for app 1\n")
    
    backfilled = 0
    for task in tasks:
        result_summary = task.get_result_summary()
        
        if not result_summary:
            print(f"⏭️  Skipping {task.task_id} (no result_summary)")
            continue
        
        # Check if files already exist
        model_safe = task.target_model.replace('/', '_').replace('\\', '_')
        results_dir = Path(__file__).parent / 'results' / model_safe / f'app{task.target_app_number}'
        
        if results_dir.exists():
            print(f"⏭️  Skipping {task.task_id} (results directory already exists)")
            continue
        
        print(f"\n📝 Processing task {task.task_id}")
        print(f"   Type: {task.analysis_type}")
        print(f"   Completed: {task.completed_at}")
        
        try:
            filepath = write_result_file(task, result_summary)
            backfilled += 1
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print(f"\n✨ Backfilled {backfilled} result files")
