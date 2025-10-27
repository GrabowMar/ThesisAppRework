#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import GeneratedApplication, AnalysisTask
from app.paths import GENERATED_APPS_DIR

app = create_app()
with app.app_context():
    # Check openai_codex-mini tasks
    print("="*70)
    print("OPENAI_CODEX-MINI ANALYSIS CHECK")
    print("="*70)
    
    codex_tasks = AnalysisTask.query.filter(
        AnalysisTask.target_model.like('%codex%')
    ).order_by(AnalysisTask.created_at.desc()).limit(5).all()
    
    print(f"\nFound {len(codex_tasks)} codex tasks (showing latest 5):\n")
    
    for task in codex_tasks:
        print(f"Task: {task.task_id}")
        print(f"  Target: {task.target_model} app{task.target_app_number}")
        print(f"  Status: {task.status.value if hasattr(task.status, 'value') else task.status}")
        
        # Check path
        expected = GENERATED_APPS_DIR / task.target_model / f"app{task.target_app_number}"
        print(f"  Expected path: {expected}")
        print(f"  Path exists: {expected.exists()}")
        
        # Check results
        print(f"  Has result_summary: {bool(task.result_summary)}")
        if task.result_summary:
            import json
            try:
                summary = json.loads(task.result_summary)
                print(f"  Summary status: {summary.get('summary', {}).get('status', 'N/A')}")
                print(f"  Total findings: {summary.get('summary', {}).get('total_findings', 0)}")
            except:
                pass
        print()
    
    # Check DB records
    print("\n" + "="*70)
    print("DATABASE RECORDS")
    print("="*70)
    
    codex_apps = GeneratedApplication.query.filter_by(model_slug='openai_codex-mini').all()
    print(f"\nopenai_codex-mini apps in DB: {len(codex_apps)}")
    for app_rec in codex_apps:
        fs_path = GENERATED_APPS_DIR / 'openai_codex-mini' / f"app{app_rec.app_number}"
        print(f"  - app{app_rec.app_number}: status={app_rec.generation_status.value if hasattr(app_rec.generation_status, 'value') else app_rec.generation_status}, exists={fs_path.exists()}")
