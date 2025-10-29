"""Diagnostic script for analysis execution failures.

This script checks for common issues that cause analysis tasks to fail:
1. Database vs filesystem mismatches (DB records without actual files)
2. Path validation issues (where are apps expected vs where they are)
3. Missing analyzer services or containers
4. Task metadata issues

Usage:
    python scripts/diagnose_analysis_failure.py
    python scripts/diagnose_analysis_failure.py --model openai_chatgpt-4o-latest --app 1
"""
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))

import argparse
from app.factory import create_app
from app.models import GeneratedApplication, AnalysisTask
from app.paths import GENERATED_APPS_DIR, PROJECT_ROOT
from sqlalchemy import desc
import socket

def check_path_exists(path: Path) -> tuple[bool, str]:
    """Check if path exists and return status message."""
    if path.exists():
        file_count = len(list(path.rglob("*.*"))) if path.is_dir() else 0
        return True, f"✅ EXISTS ({file_count} files)" if path.is_dir() else "✅ EXISTS"
    return False, "❌ MISSING"

def check_service_health(service_name: str, port: int) -> bool:
    """Check if analyzer service is reachable."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.5)
            return s.connect_ex(('localhost', port)) == 0
    except Exception:
        return False

def diagnose_all():
    """Run full diagnostic check."""
    app = create_app()
    
    with app.app_context():
        print("=" * 80)
        print("ANALYZER DIAGNOSTIC REPORT")
        print("=" * 80)
        print()
        
        # 1. Database vs Filesystem Check
        print("1. DATABASE vs FILESYSTEM MISMATCH CHECK")
        print("-" * 80)
        
        all_apps = GeneratedApplication.query.all()
        if not all_apps:
            print("⚠️  No GeneratedApplication records in database")
        else:
            mismatches = []
            for app_record in all_apps:
                app_dir = GENERATED_APPS_DIR / app_record.model_slug / f"app{app_record.app_number}"
                exists, status = check_path_exists(app_dir)
                
                if not exists:
                    mismatches.append({
                        'model': app_record.model_slug,
                        'app_number': app_record.app_number,
                        'db_id': app_record.id,
                        'expected_path': str(app_dir),
                        'created_at': app_record.created_at
                    })
                    print(f"❌ MISMATCH: {app_record.model_slug}/app{app_record.app_number}")
                    print(f"   DB Record: ✅ (id={app_record.id}, created={app_record.created_at})")
                    print(f"   Filesystem: {status}")
                    print(f"   Expected: {app_dir}")
                else:
                    print(f"✅ OK: {app_record.model_slug}/app{app_record.app_number}")
                    print(f"   Path: {app_dir} {status}")
                print()
            
            if mismatches:
                print(f"\n⚠️  FOUND {len(mismatches)} MISMATCHES")
                print("   These DB records have no corresponding filesystem directories.")
                print("   Analysis will fail with 'Target path does not exist' error.")
                print("\nRECOMMENDED ACTION:")
                print("   Generate applications using:")
                for mm in mismatches[:3]:  # Show first 3
                    print(f"     POST /api/gen/generate -d '{{\"model_slug\":\"{mm['model']}\",\"app_num\":{mm['app_number']},\"template_id\":1}}'")
                if len(mismatches) > 3:
                    print(f"     ... and {len(mismatches) - 3} more")
        
        print()
        
        # 2. Analyzer Services Check
        print("2. ANALYZER SERVICES CHECK")
        print("-" * 80)
        
        services = {
            'static-analyzer': 2001,
            'dynamic-analyzer': 2002,
            'performance-tester': 2003,
            'ai-analyzer': 2004
        }
        
        all_healthy = True
        for service_name, port in services.items():
            is_up = check_service_health(service_name, port)
            status = "✅ HEALTHY" if is_up else "❌ DOWN"
            print(f"{status}: {service_name} (localhost:{port})")
            if not is_up:
                all_healthy = False
        
        if not all_healthy:
            print("\n⚠️  Some analyzer services are DOWN")
            print("RECOMMENDED ACTION:")
            print("  Start services: python analyzer/analyzer_manager.py start")
        
        print()
        
        # 3. Recent Failed Tasks Check
        print("3. RECENT FAILED TASKS ANALYSIS")
        print("-" * 80)
        
        failed_tasks = AnalysisTask.query.filter(
            AnalysisTask.status.in_(['failed', 'completed'])
        ).order_by(desc(AnalysisTask.completed_at)).limit(10).all()
        
        if not failed_tasks:
            print("No recent tasks found")
        else:
            for task in failed_tasks:
                # Check if has 0 findings
                result_summary = task.get_result_summary() if hasattr(task, 'get_result_summary') else {}
                total_findings = result_summary.get('summary', {}).get('total_findings', 0)
                
                if total_findings == 0 or task.status.value == 'failed':
                    print(f"\n❌ Task: {task.task_id}")
                    print(f"   Status: {task.status.value}")
                    print(f"   Target: {task.target_model}/app{task.target_app_number}")
                    print(f"   Findings: {total_findings}")
                    print(f"   Duration: {task.actual_duration}s" if task.actual_duration else "   Duration: None")
                    
                    # Check if target exists
                    app_dir = GENERATED_APPS_DIR / task.target_model / f"app{task.target_app_number}"
                    exists, status = check_path_exists(app_dir)
                    print(f"   Target Path: {status}")
                    
                    # Check for error
                    if result_summary.get('error'):
                        print(f"   Error: {result_summary['error'][:100]}")
        
        print()
        
        # 4. Path Resolution Check
        print("4. PATH RESOLUTION CHECK")
        print("-" * 80)
        print(f"Generated Apps Directory: {GENERATED_APPS_DIR}")
        print(f"  Exists: {GENERATED_APPS_DIR.exists()}")
        
        if GENERATED_APPS_DIR.exists():
            model_dirs = list(GENERATED_APPS_DIR.iterdir())
            print(f"  Model directories: {len(model_dirs)}")
            if model_dirs:
                for md in model_dirs[:5]:  # Show first 5
                    if md.is_dir():
                        app_dirs = [d for d in md.iterdir() if d.is_dir() and d.name.startswith('app')]
                        print(f"    {md.name}: {len(app_dirs)} apps")
        else:
            print("  ⚠️  Directory does not exist!")
        
        print()
        print("=" * 80)
        print("DIAGNOSTIC COMPLETE")
        print("=" * 80)

def diagnose_specific(model_slug: str, app_number: int):
    """Diagnose a specific model/app combination."""
    app = create_app()
    
    with app.app_context():
        print("=" * 80)
        print(f"DIAGNOSTIC: {model_slug}/app{app_number}")
        print("=" * 80)
        print()
        
        # 1. Database Check
        print("1. DATABASE CHECK")
        print("-" * 80)
        app_record = GeneratedApplication.query.filter_by(
            model_slug=model_slug,
            app_number=app_number
        ).first()
        
        if app_record:
            print(f"✅ GeneratedApplication record EXISTS")
            print(f"   ID: {app_record.id}")
            print(f"   Provider: {app_record.provider}")
            print(f"   Created: {app_record.created_at}")
            print(f"   Generation Status: {app_record.generation_status.value if app_record.generation_status else 'None'}")
        else:
            print(f"❌ No GeneratedApplication record in database")
        
        print()
        
        # 2. Filesystem Check
        print("2. FILESYSTEM CHECK")
        print("-" * 80)
        app_dir = GENERATED_APPS_DIR / model_slug / f"app{app_number}"
        exists, status = check_path_exists(app_dir)
        
        print(f"Expected path: {app_dir}")
        print(f"Status: {status}")
        
        if exists:
            # Show directory structure
            subdirs = [d for d in app_dir.iterdir() if d.is_dir()]
            files = [f for f in app_dir.rglob("*") if f.is_file()]
            print(f"Subdirectories: {len(subdirs)} - {[d.name for d in subdirs]}")
            print(f"Total files: {len(files)}")
        
        print()
        
        # 3. Analysis Tasks Check
        print("3. ANALYSIS TASKS FOR THIS APP")
        print("-" * 80)
        tasks = AnalysisTask.query.filter_by(
            target_model=model_slug,
            target_app_number=app_number
        ).order_by(desc(AnalysisTask.created_at)).limit(5).all()
        
        if not tasks:
            print("No analysis tasks found for this app")
        else:
            for task in tasks:
                result_summary = task.get_result_summary() if hasattr(task, 'get_result_summary') else {}
                total_findings = result_summary.get('summary', {}).get('total_findings', 0)
                error = result_summary.get('error')
                
                print(f"\nTask: {task.task_id}")
                print(f"  Status: {task.status.value}")
                print(f"  Created: {task.created_at}")
                print(f"  Findings: {total_findings}")
                if error:
                    print(f"  Error: {error[:150]}")
        
        print()
        
        # 4. Recommendation
        print("4. RECOMMENDATION")
        print("-" * 80)
        
        if app_record and not exists:
            print("⚠️  DB record exists but filesystem is MISSING")
            print("\nYou need to generate the application:")
            print(f"  curl -X POST http://localhost:5000/api/gen/generate \\")
            print(f"    -H 'Authorization: Bearer YOUR_TOKEN' \\")
            print(f"    -H 'Content-Type: application/json' \\")
            print(f"    -d '{{\"model_slug\":\"{model_slug}\",\"app_num\":{app_number},\"template_id\":1}}'")
        elif not app_record and exists:
            print("⚠️  Filesystem exists but DB record is MISSING")
            print("This shouldn't happen - may need to sync DB from filesystem")
        elif not app_record and not exists:
            print("❌ Neither DB record nor filesystem exists")
            print("You need to generate the application first")
        else:
            print("✅ Everything looks good - both DB and filesystem exist")
            print("If analysis still fails, check:")
            print("  - Analyzer services are running (python analyzer/analyzer_manager.py start)")
            print("  - Celery workers are running (celery -A app.tasks worker)")
        
        print()
        print("=" * 80)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Diagnose analysis execution failures')
    parser.add_argument('--model', help='Specific model slug to diagnose')
    parser.add_argument('--app', type=int, help='Specific app number to diagnose')
    
    args = parser.parse_args()
    
    if args.model and args.app:
        diagnose_specific(args.model, args.app)
    else:
        diagnose_all()
