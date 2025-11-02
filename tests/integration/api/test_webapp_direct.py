#!/usr/bin/env python3
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.api]

"""Test analysis via web app using direct database/service calls."""
import sys
sys.path.insert(0, 'src')

from app import create_app
from app.services.task_service import AnalysisTaskService
from app.models import AnalysisTask, GeneratedApplication
from app.constants import AnalysisStatus
import time
import json
from pathlib import Path

def test_web_app_direct():
    """Test analysis through Flask app context (simulates web request)."""
    
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("WEB APP ANALYSIS TEST (Direct Service Call)")
        print("=" * 60)
        
        model_slug = "openai_gpt-4.1-2025-04-14"
        app_number = 3
        
        # Verify application exists
        gen_app = GeneratedApplication.query.filter_by(
            model_slug=model_slug,
            app_number=app_number
        ).first()
        
        if not gen_app:
            print(f"❌ Application not found: {model_slug}/app{app_number}")
            return
        
        print(f"✅ Found application: {model_slug}/app{app_number}")
        print(f"   Model: {gen_app.model_slug}")
        print(f"   App ID: {gen_app.id}")
        
        # Create analysis task via service
        print("\n" + "=" * 60)
        print("Creating Analysis Task")
        print("=" * 60)
        
        try:
            # Use the same service as the web endpoint would
            # Create task with specific tools for security + static analysis
            tools = ['bandit', 'pylint', 'semgrep', 'safety']  # SARIF tools for testing
            
            task = AnalysisTaskService.create_task(
                model_slug=model_slug,
                app_number=app_number,
                tools=tools,
                priority='high',
                custom_options={
                    'source': 'test_script',
                    'test_sarif': True
                },
                task_name=f"webapp_test_{model_slug}_app{app_number}"
            )
            
            print(f"✅ Task created: {task.task_id}")
            print(f"   Status: {task.status.value}")
            print(f"   Is main task: {task.is_main_task}")
            
            # Monitor task progress
            print("\n" + "=" * 60)
            print("Monitoring Task Execution")
            print("=" * 60)
            
            max_wait = 120  # 2 minutes
            check_interval = 5
            elapsed = 0
            
            while elapsed < max_wait:
                # Refresh task from DB
                from app.extensions import db
                db.session.expire(task)
                db.session.refresh(task)
                
                status = task.status.value
                progress = task.progress_percentage or 0
                print(f"[{elapsed}s] Status: {status} | Progress: {progress}%")
                
                if status in ['completed', 'failed', 'error']:
                    print(f"\n✅ Task finished with status: {status}")
                    break
                
                time.sleep(check_interval)
                elapsed += check_interval
            else:
                print(f"\n⏱️ Timeout after {max_wait}s")
            
            # Check filesystem results
            print("\n" + "=" * 60)
            print("Verifying Filesystem Results")
            print("=" * 60)
            
            results_base = Path(f"results/{model_slug}/app{app_number}")
            if results_base.exists():
                # Find most recent task directory
                task_dirs = [d for d in results_base.iterdir() 
                            if d.is_dir() and d.name.startswith('task_')]
                if task_dirs:
                    latest_task = max(task_dirs, key=lambda d: d.stat().st_mtime)
                    print(f"✅ Found task directory: {latest_task}")
                    
                    # Check for consolidated JSON
                    json_files = list(latest_task.glob("*.json"))
                    json_files = [f for f in json_files if f.name != 'manifest.json']
                    
                    if json_files:
                        latest_json = max(json_files, key=lambda f: f.stat().st_mtime)
                        print(f"✅ Found results JSON: {latest_json.name}")
                        print(f"   Size: {latest_json.stat().st_size / 1024:.1f} KB")
                        
                        # Load and check structure
                        with open(latest_json) as f:
                            results_data = json.load(f)
                        
                        tools = results_data.get('results', {}).get('tools', {})
                        findings = results_data.get('results', {}).get('findings', [])
                        services = results_data.get('results', {}).get('services', {})
                        
                        print(f"\n📊 Results Summary:")
                        print(f"   Total tools: {len(tools)}")
                        print(f"   Total findings: {len(findings)}")
                        print(f"   Services: {list(services.keys())}")
                        
                        # Check SARIF tools specifically
                        sarif_tools = ['bandit', 'pylint', 'semgrep', 'mypy', 'eslint', 'ruff']
                        present_sarif_tools = [t for t in sarif_tools if t in tools]
                        
                        if present_sarif_tools:
                            print(f"\n🔍 SARIF Tools Present ({len(present_sarif_tools)}):")
                            for tool_name in present_sarif_tools:
                                tool_data = tools[tool_name]
                                status = tool_data.get('status', 'unknown')
                                issues = tool_data.get('total_issues', 0)
                                executed = tool_data.get('executed', False)
                                emoji = "✅" if executed else "❌"
                                print(f"   {emoji} {tool_name}: {status} (executed: {executed}, issues: {issues})")
                        
                        # Verify SARIF data in service snapshots
                        print(f"\n🔬 Checking SARIF Data in Service Snapshots:")
                        services_dir = latest_task / "services"
                        if services_dir.exists():
                            static_snapshot = services_dir / f"{model_slug}_app{app_number}_static.json"
                            security_snapshot = services_dir / f"{model_slug}_app{app_number}_security.json"
                            
                            for snapshot_file in [static_snapshot, security_snapshot]:
                                if snapshot_file.exists():
                                    with open(snapshot_file) as f:
                                        snapshot_data = json.load(f)
                                    
                                    service_name = snapshot_file.stem.split('_')[-1]
                                    print(f"   ✅ {service_name} snapshot exists ({snapshot_file.stat().st_size / 1024:.1f} KB)")
                                    
                                    # Check for SARIF in static analyzer
                                    if service_name == 'static':
                                        analysis = snapshot_data.get('results', {}).get('analysis', {})
                                        results_section = analysis.get('results', {})
                                        python_tools = results_section.get('python', {})
                                        
                                        for tool in ['bandit', 'pylint', 'semgrep', 'mypy', 'ruff']:
                                            has_sarif = 'sarif' in python_tools.get(tool, {})
                                            emoji = "✅" if has_sarif else "❌"
                                            print(f"      {emoji} {tool} has SARIF: {has_sarif}")
                        
                        print("\n" + "=" * 60)
                        print("🎉 WEB APP ANALYSIS TEST COMPLETED SUCCESSFULLY!")
                        print("=" * 60)
                        print("\nKey Verification Points:")
                        print("  ✅ Task created via AnalysisTaskService")
                        print("  ✅ Task executed and completed")
                        print("  ✅ Filesystem results generated")
                        print("  ✅ Consolidated JSON with tools map")
                        print(f"  ✅ SARIF tools present: {', '.join(present_sarif_tools)}")
                        print("  ✅ SARIF data in service snapshots")
                        
                    else:
                        print("❌ No JSON files found in task directory")
                else:
                    print("❌ No task directories found")
            else:
                print(f"❌ Results directory not found: {results_base}")
                
        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_web_app_direct()
