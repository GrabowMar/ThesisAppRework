import pytest

pytestmark = [pytest.mark.integration, pytest.mark.analyzer]

"""
Test comprehensive analysis with all available tools after enabling container delegation
"""
import os
import sys
import json
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app.factory import create_app
from app.extensions import db
from app.models import AnalysisTask
from app.services.service_locator import ServiceLocator

def main():
    print("=" * 80)
    print("COMPREHENSIVE ANALYSIS TEST - ALL TOOLS")
    print("=" * 80)
    
    app = create_app()
    
    with app.app_context():
        # Initialize services
        ServiceLocator.initialize(app)
        
        # Test parameters
        model_slug = "openai_gpt-4.1-2025-04-14"
        app_number = 1
        
        # Define comprehensive tool set
        tools = [
            # Static analysis - Python
            "bandit",
            "safety", 
            "pylint",
            "flake8",
            "mypy",
            
            # Static analysis - JavaScript (if app has JS)
            "eslint",
        ]
        
        print(f"\nTarget: {model_slug}/app{app_number}")
        print(f"Tools: {', '.join(tools)}")
        print()
        
        # Ensure test app exists
        from app.models import GeneratedApplication, AnalyzerConfiguration
        from app.constants import AnalysisStatus
        from datetime import datetime, timezone
        import uuid
        
        test_app = GeneratedApplication.query.filter_by(
            model_slug=model_slug,
            app_number=app_number
        ).first()
        
        if not test_app:
            print("Creating GeneratedApplication record...")
            test_app = GeneratedApplication(
                model_slug=model_slug,
                app_number=app_number,
                template_slug='crud_todo_list',
                status='completed',
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(test_app)
            db.session.commit()
        
        # Ensure analyzer config exists
        config = AnalyzerConfiguration.query.filter_by(is_default=True).first()
        if not config:
            print("Creating default analyzer configuration...")
            config = AnalyzerConfiguration(
                name='default',
                description='Default analyzer configuration',
                config_data='{}',
                is_default=True,
                is_active=True
            )
            db.session.add(config)
            db.session.commit()
        
        # Create analysis task
        print("Creating analysis task...")
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        
        # Store tools in metadata with correct structure
        # The task executor expects 'selected_tools' in custom_options
        metadata = {
            'analysis_type': 'comprehensive',
            'custom_options': {
                'selected_tools': tools  # Use tool names directly (strings)
            }
        }
        
        task = AnalysisTask(
            task_id=task_id,
            target_model=model_slug,
            target_app_number=app_number,
            task_name='unified',
            status=AnalysisStatus.PENDING,
            analyzer_config_id=config.id,
            is_main_task=True,
            metadata=json.dumps(metadata),
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(task)
        db.session.commit()
        
        if not task:
            print("[FAIL] Failed to create task")
            return 1
        
        print(f"[OK] Task created: {task.task_id}")
        print(f"     Status: {task.status}")
        print(f"     Tools: {len(tools)}")
        print()
        
        # Wait for task to complete
        print("Waiting for task execution...")
        max_wait = 120  # 2 minutes
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            db.session.refresh(task)
            
            if task.status in ['completed', 'failed', 'error']:
                break
            
            # Show progress
            elapsed = int(time.time() - start_time)
            print(f"\r  [{elapsed}s] Status: {task.status:15s}", end='', flush=True)
            time.sleep(2)
        
        print()  # New line after progress
        
        # Get final status
        db.session.refresh(task)
        
        print()
        print("=" * 80)
        print("TASK RESULTS")
        print("=" * 80)
        print(f"Task ID: {task.task_id}")
        print(f"Status: {task.status}")
        if hasattr(task, 'duration_seconds') and task.duration_seconds:
            print(f"Duration: {task.duration_seconds:.2f}s")
        elif task.completed_at and task.started_at:
            duration = (task.completed_at - task.started_at).total_seconds()
            print(f"Duration: {duration:.2f}s")
        else:
            print("Duration: N/A")
        print()
        
        # Check result file
        results_dir = Path(__file__).parent / "results" / model_slug / f"app{app_number}" / "analysis" / task.task_id
        consolidated_path = results_dir / "consolidated.json"
        
        if consolidated_path.exists():
            print(f"[OK] Results file exists: {consolidated_path}")
            print()
            
            # Parse and display results
            with open(consolidated_path, 'r') as f:
                results = json.load(f)
            
            print("-" * 80)
            print("SUMMARY")
            print("-" * 80)
            summary = results.get('summary', {})
            print(f"Total findings: {summary.get('total_findings', 0)}")
            print(f"Tools executed: {summary.get('tools_executed', 0)}")
            print(f"Tools failed: {len(summary.get('tools_failed', []))}")
            print(f"Status: {summary.get('status', 'unknown')}")
            print()
            
            # Show tool results
            print("-" * 80)
            print("TOOL RESULTS")
            print("-" * 80)
            tool_results = results.get('tools', {})
            
            for tool_name in tools:
                tool_data = tool_results.get(tool_name, {})
                status = tool_data.get('status', 'unknown')
                executed = tool_data.get('executed', False)
                findings_count = tool_data.get('findings_count', 0)
                error = tool_data.get('error', '')
                
                # Determine icon
                if 'success' in status.lower() or executed:
                    icon = "[OK]"
                elif 'not_available' in status.lower():
                    icon = "[FAIL]"
                else:
                    icon = "[WARN]"
                
                print(f"{icon} {tool_name:20s} | executed={str(executed):5s} | findings={findings_count:3d} | status={status}")
                
                if error and executed:
                    print(f"   Error: {error[:100]}")
            
            print()
            
            # Verdict
            print("=" * 80)
            print("VERDICT")
            print("=" * 80)
            
            any_executed = any(
                tool_results.get(tool, {}).get('executed', False) 
                for tool in tools
            )
            
            all_not_available = all(
                'not_available' in tool_results.get(tool, {}).get('status', '').lower()
                for tool in tools
            )
            
            total_findings = summary.get('total_findings', 0)
            
            if any_executed and not all_not_available:
                print("[SUCCESS] Tools are executing!")
                print(f"   - At least some tools ran successfully")
                print(f"   - Total findings: {total_findings}")
                
                if total_findings > 0:
                    print("   - Security/quality issues detected (expected behavior)")
                else:
                    print("   - No issues found (code may be clean or tools need tuning)")
                
                return 0
            else:
                print("[FAILURE] Tools still not executing properly")
                print("   - All tools showing 'not_available' status")
                print("   - Container delegation may not be working")
                print()
                print("   Debugging steps:")
                print("   1. Check ORCHESTRATOR_USE_CONTAINER_TOOLS=1 in .env")
                print("   2. Verify Flask loaded the .env file")
                print("   3. Check analyzer containers: python analyzer/analyzer_manager.py status")
                print("   4. Review Flask logs for delegation messages")
                return 1
            
        else:
            print(f"[FAIL] Results file not found: {consolidated_path}")
            print()
            print("   Check:")
            print("   1. Task execution service is running")
            print("   2. Flask logs for errors")
            print("   3. Task status in database")
            return 1

if __name__ == '__main__':
    sys.exit(main())
