#!/usr/bin/env python3
"""
Diagnostic script to verify web app analysis result file generation.

This script checks:
1. Task execution service is properly initialized
2. Result files are generated in correct location (results/{model}/app{N}/task_{task_id}/)
3. Files match the expected consolidated structure with metadata, summary, services, tools, findings
4. Manifest.json is created
"""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from app.factory import create_app
from app.models import AnalysisTask
from app.extensions import db
from app.paths import RESULTS_DIR


def check_task_execution_service():
    """Verify task execution service is initialized."""
    print("\n=== Task Execution Service Check ===")
    try:
        from app.services.task_execution_service import task_execution_service
        if task_execution_service is None:
            print("❌ Task execution service is NOT initialized")
            return False
        
        print(f"✅ Task execution service initialized")
        print(f"   - Running: {task_execution_service._running}")
        print(f"   - Poll interval: {task_execution_service.poll_interval}s")
        print(f"   - Batch size: {task_execution_service.batch_size}")
        return True
    except Exception as e:
        print(f"❌ Error checking task execution service: {e}")
        return False


def check_recent_tasks():
    """Check recent analysis tasks and their result files."""
    print("\n=== Recent Analysis Tasks ===")
    try:
        # Get 5 most recent completed tasks
        tasks = AnalysisTask.query.order_by(AnalysisTask.created_at.desc()).limit(10).all()
        
        if not tasks:
            print("ℹ️  No analysis tasks found in database")
            return
        
        print(f"Found {len(tasks)} recent tasks:\n")
        
        for task in tasks:
            print(f"Task: {task.task_id}")
            print(f"  Model: {task.target_model}, App: {task.target_app_number}")
            print(f"  Status: {task.status.value if task.status else 'unknown'}")
            print(f"  Created: {task.created_at}")
            print(f"  Completed: {task.completed_at or 'N/A'}")
            
            # Check for result file
            expected_dir = RESULTS_DIR / task.target_model / f"app{task.target_app_number}" / f"task_{task.task_id}"
            legacy_dir = RESULTS_DIR / task.target_model / f"app{task.target_app_number}" / "analysis" / task.task_id
            
            if expected_dir.exists():
                result_files = list(expected_dir.glob("*.json"))
                manifest = expected_dir / "manifest.json"
                
                if result_files:
                    print(f"  ✅ Result files found in {expected_dir}:")
                    for f in result_files:
                        size_kb = f.stat().st_size / 1024
                        print(f"     - {f.name} ({size_kb:.1f} KB)")
                        
                        # Validate structure
                        if f.name != "manifest.json":
                            validate_result_file(f)
                    
                    if manifest.exists():
                        print(f"     - manifest.json ✅")
                else:
                    print(f"  ⚠️  Directory exists but no JSON files found")
            elif legacy_dir.exists():
                print(f"  ⚠️  Files found in LEGACY location: {legacy_dir}")
                print(f"     (Should be migrated to: {expected_dir})")
            else:
                print(f"  ❌ No result files found")
                print(f"     Expected location: {expected_dir}")
                
                # Check task metadata for errors
                metadata = task.get_metadata()
                if 'result_file_error' in metadata:
                    print(f"     Error recorded: {metadata['result_file_error']}")
                if 'result_file_warning' in metadata:
                    print(f"     Warning: {metadata['result_file_warning']}")
            
            print()
            
    except Exception as e:
        print(f"❌ Error checking tasks: {e}")
        import traceback
        traceback.print_exc()


def validate_result_file(filepath: Path):
    """Validate that result file has expected structure."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        required_sections = {
            'metadata': ['model_slug', 'app_number', 'analysis_type', 'timestamp'],
            'results': ['task', 'summary', 'services', 'tools', 'findings']
        }
        
        issues = []
        
        # Check top-level structure
        if 'metadata' not in data:
            issues.append("Missing 'metadata' section")
        elif isinstance(data['metadata'], dict):
            for field in required_sections['metadata']:
                if field not in data['metadata']:
                    issues.append(f"Missing metadata.{field}")
        
        if 'results' not in data:
            issues.append("Missing 'results' section")
        elif isinstance(data['results'], dict):
            for section in required_sections['results']:
                if section not in data['results']:
                    issues.append(f"Missing results.{section}")
        
        if issues:
            print(f"     ⚠️  Structure issues: {', '.join(issues)}")
        else:
            # Show some stats
            results = data.get('results', {})
            summary = results.get('summary', {})
            print(f"     ✅ Valid structure - {summary.get('total_findings', 0)} findings, {summary.get('tools_executed', 0)} tools")
            
    except json.JSONDecodeError as e:
        print(f"     ❌ Invalid JSON: {e}")
    except Exception as e:
        print(f"     ⚠️  Validation error: {e}")


def check_result_directory_structure():
    """Check overall results directory structure."""
    print("\n=== Results Directory Structure ===")
    
    if not RESULTS_DIR.exists():
        print(f"❌ Results directory not found: {RESULTS_DIR}")
        return
    
    print(f"Results directory: {RESULTS_DIR}\n")
    
    model_dirs = [d for d in RESULTS_DIR.iterdir() if d.is_dir()]
    print(f"Found {len(model_dirs)} model directories:")
    
    for model_dir in sorted(model_dirs):
        print(f"\n  📁 {model_dir.name}")
        
        app_dirs = [d for d in model_dir.iterdir() if d.is_dir() and d.name.startswith('app')]
        for app_dir in sorted(app_dirs):
            print(f"    📁 {app_dir.name}")
            
            # Count task directories
            task_dirs = [d for d in app_dir.iterdir() if d.is_dir() and d.name.startswith('task_')]
            legacy_analysis_dir = app_dir / "analysis"
            
            if task_dirs:
                print(f"       ✅ {len(task_dirs)} task directories (correct structure)")
                for task_dir in sorted(task_dirs)[:3]:  # Show first 3
                    json_files = list(task_dir.glob("*.json"))
                    print(f"          - {task_dir.name}: {len(json_files)} JSON files")
            
            if legacy_analysis_dir.exists() and legacy_analysis_dir.is_dir():
                legacy_tasks = [d for d in legacy_analysis_dir.iterdir() if d.is_dir()]
                print(f"       ⚠️  {len(legacy_tasks)} tasks in LEGACY /analysis/ directory")


def main():
    """Run all diagnostic checks."""
    print("=" * 70)
    print("Web App Analysis Result Generation Diagnostic")
    print("=" * 70)
    
    # Create app context
    app = create_app()
    
    with app.app_context():
        # Run checks
        service_ok = check_task_execution_service()
        check_recent_tasks()
        check_result_directory_structure()
        
        # Summary
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        
        if service_ok:
            print("✅ Task execution service is running")
            print("✅ Web app analyses should generate result files")
            print(f"✅ Expected location: results/{{model}}/app{{N}}/task_{{task_id}}/")
        else:
            print("❌ Task execution service is NOT running")
            print("❌ Web app analyses will NOT generate result files")
            print("   Check logs for initialization errors")
        
        print("\nTo test:")
        print("1. Start the Flask app: python src/main.py")
        print("2. Navigate to /analysis/create in the web UI")
        print("3. Submit an analysis")
        print("4. Check logs for 'Successfully wrote result files to disk'")
        print("5. Verify files appear in results/{model}/app{N}/task_{task_id}/")


if __name__ == "__main__":
    main()
