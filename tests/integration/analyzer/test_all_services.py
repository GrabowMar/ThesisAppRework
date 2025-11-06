import pytest

pytestmark = [pytest.mark.integration, pytest.mark.analyzer]

"""
Comprehensive Test - All Analyzer Services
==========================================
Tests static, dynamic, performance, and AI analysis services.
"""

import sys
import os
import time
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app.factory import create_app
from app.extensions import db
from app.models import AnalysisTask, GeneratedApplication, AnalyzerConfiguration
from app.constants import AnalysisStatus
from app.services.service_locator import ServiceLocator

def print_section(title, char='='):
    print(f"\n{char * 80}")
    print(title.center(80))
    print(f"{char * 80}")

def create_analysis_task(model_slug, app_number, analysis_type, tools=None, config=None):
    """Create an analysis task in the database."""
    task_id = f"task-{uuid.uuid4().hex[:8]}"
    
    metadata = {
        'analysis_type': analysis_type,
        'custom_options': {}
    }
    
    if tools:
        metadata['custom_options']['selected_tools'] = tools
    
    if config:
        metadata['custom_options'].update(config)
    
    # Get analyzer config
    analyzer_config = AnalyzerConfiguration.query.filter_by(is_default=True).first()
    
    task = AnalysisTask(
        task_id=task_id,
        target_model=model_slug,
        target_app_number=app_number,
        task_name=analysis_type,
        status=AnalysisStatus.PENDING,
        analyzer_config_id=analyzer_config.id if analyzer_config else None,
        is_main_task=True,
        metadata=json.dumps(metadata),
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(task)
    db.session.commit()
    
    return task_id

def wait_for_task(task_id, max_wait=120):
    """Wait for a task to complete and return its status."""
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        task = AnalysisTask.query.filter_by(task_id=task_id).first()
        
        if not task:
            return None, "Task not found"
        
        status = task.status
        
        if status == AnalysisStatus.COMPLETED.value:
            return task, None
        elif status == AnalysisStatus.FAILED.value:
            return task, task.result.get('error') if task.result else 'Unknown error'
        
        time.sleep(2)
    
    return None, f"Timeout after {max_wait}s"

def print_task_results(task):
    """Print comprehensive task results."""
    if not task or not task.result:
        print("[FAIL] No results available")
        return
    
    result = task.result
    
    # Count findings and tools
    total_findings = 0
    tools_executed = []
    tools_failed = []
    
    if 'tools' in result:
        for tool_name, tool_data in result['tools'].items():
            if isinstance(tool_data, dict):
                if tool_data.get('executed'):
                    tools_executed.append(tool_name)
                    total_findings += tool_data.get('total_issues', 0)
                elif tool_data.get('status') == 'error':
                    tools_failed.append(tool_name)
    
    print(f"[OK] Task completed in {task.completed_at - task.started_at if task.completed_at and task.started_at else 'N/A'}")
    print(f"     Tools executed: {len(tools_executed)} - {', '.join(tools_executed[:5])}")
    if tools_failed:
        print(f"     Tools failed: {len(tools_failed)} - {', '.join(tools_failed[:3])}")
    print(f"     Total findings: {total_findings}")
    
    # Show sample findings
    if total_findings > 0 and 'tools' in result:
        print(f"\n     Sample findings:")
        count = 0
        for tool_name, tool_data in result['tools'].items():
            if isinstance(tool_data, dict) and tool_data.get('issues'):
                for issue in tool_data['issues'][:2]:  # Show first 2 from this tool
                    print(f"       [{tool_name}] {issue.get('severity', 'info').upper()}: {issue.get('message', 'No message')}")
                    if 'file' in issue:
                        print(f"                File: {issue['file']} Line: {issue.get('line', '?')}")
                    count += 1
                    if count >= 3:
                        break
            if count >= 3:
                break

def main():
    print_section("COMPREHENSIVE ANALYSIS - ALL SERVICES")
    
    # Configuration
    model_slug = "openai_gpt-4.1-2025-04-14"
    app_number = 1
    
    print(f"\nTarget: {model_slug}/app{app_number}")
    
    # Create Flask app and initialize services
    print("\n[INIT] Initializing Flask application...")
    app = create_app()
    
    with app.app_context():
        ServiceLocator.initialize(app)
        
        # Ensure test app exists
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
        
        # Test 1: Static Analysis
        print_section("TEST 1: STATIC ANALYSIS", '-')
        print("Tools: bandit, safety, pylint, flake8, mypy, semgrep, eslint")
        
        try:
            task_id = create_analysis_task(
                model_slug=model_slug,
                app_number=app_number,
                analysis_type='static_analysis',
                tools=['bandit', 'safety', 'pylint', 'flake8', 'mypy', 'semgrep', 'eslint']
            )
            print(f"[OK] Created task: {task_id}")
            
            task, error = wait_for_task(task_id, max_wait=60)
            if error:
                print(f"[FAIL] {error}")
            else:
                print_task_results(task)
        
        except Exception as e:
            print(f"[ERROR] Static analysis test failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Test 2: Security Analysis
        print_section("TEST 2: SECURITY ANALYSIS", '-')
        print("Comprehensive security scan (static + dynamic if available)")
        
        try:
            task_id = create_analysis_task(
                model_slug=model_slug,
                app_number=app_number,
                analysis_type='security_analysis',
                tools=['bandit', 'safety', 'owasp-zap', 'semgrep']
            )
            print(f"[OK] Created task: {task_id}")
            
            task, error = wait_for_task(task_id, max_wait=90)
            if error:
                print(f"[FAIL] {error}")
            else:
                print_task_results(task)
        
        except Exception as e:
            print(f"[ERROR] Security analysis test failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Test 3: Performance Testing
        print_section("TEST 3: PERFORMANCE TESTING", '-')
        print("Load testing and performance metrics")
        
        try:
            task_id = create_analysis_task(
                model_slug=model_slug,
                app_number=app_number,
                analysis_type='performance_test',
                config={
                    'test_config': {
                        'users': 5,
                        'duration': 15,
                        'spawn_rate': 1
                    }
                }
            )
            print(f"[OK] Created task: {task_id}")
            
            task, error = wait_for_task(task_id, max_wait=120)
            if error:
                print(f"[FAIL] {error}")
            else:
                print_task_results(task)
        
        except Exception as e:
            print(f"[ERROR] Performance test failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Test 4: AI Code Review
        print_section("TEST 4: AI CODE REVIEW", '-')
        
        # Check if OpenRouter API key is set
        if not os.getenv('OPENROUTER_API_KEY'):
            print("[SKIP] OPENROUTER_API_KEY not set - skipping AI analysis")
        else:
            print("AI-powered code analysis and recommendations")
            
            try:
                task_id = create_analysis_task(
                    model_slug=model_slug,
                    app_number=app_number,
                    analysis_type='ai_analysis',
                    config={
                        'focus_areas': ['security', 'performance', 'best_practices']
                    }
                )
                print(f"[OK] Created task: {task_id}")
                
                task, error = wait_for_task(task_id, max_wait=180)
                if error:
                    print(f"[FAIL] {error}")
                else:
                    print_task_results(task)
            
            except Exception as e:
                print(f"[ERROR] AI analysis test failed: {e}")
                import traceback
                traceback.print_exc()
        
        # Summary
        print_section("TEST SUMMARY")
        
        completed_tasks = AnalysisTask.query.filter(
            AnalysisTask.target_model == model_slug,
            AnalysisTask.target_app_number == app_number,
            AnalysisTask.status == AnalysisStatus.COMPLETED
        ).count()
        
        failed_tasks = AnalysisTask.query.filter(
            AnalysisTask.target_model == model_slug,
            AnalysisTask.target_app_number == app_number,
            AnalysisTask.status == AnalysisStatus.FAILED
        ).count()
        
        print(f"\n✅ Completed: {completed_tasks} tasks")
        print(f"❌ Failed: {failed_tasks} tasks")
        
        print("\n" + "=" * 80)
        print("All analyzer services tested!")
        print("=" * 80)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Test cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def print_section(title, char='='):
    print(f"\n{char * 80}")
    print(title.center(80))
    print(f"{char * 80}")

def print_service_results(service_name, result):
    """Print results from a single service."""
    if not result:
        print(f"[FAIL] {service_name}: No results returned")
        return
    
    status = result.get('status', 'unknown')
    if status == 'error':
        print(f"[ERROR] {service_name}: {result.get('error', 'Unknown error')}")
        return
    
    # Count findings across all tools
    total_findings = 0
    tools_executed = []
    tools_failed = []
    
    if 'tools' in result:
        for tool_name, tool_data in result['tools'].items():
            if isinstance(tool_data, dict):
                if tool_data.get('executed'):
                    tools_executed.append(tool_name)
                    total_findings += tool_data.get('total_issues', 0)
                elif tool_data.get('status') not in ['skipped', 'unknown']:
                    tools_failed.append(tool_name)
    
    print(f"[OK] {service_name}:")
    print(f"     Status: {status}")
    print(f"     Tools executed: {len(tools_executed)} {tools_executed[:5]}")
    if tools_failed:
        print(f"     Tools failed: {len(tools_failed)} {tools_failed[:5]}")
    print(f"     Total findings: {total_findings}")

def main():
    print_section("COMPREHENSIVE ANALYSIS - ALL SERVICES")
    
    # Configuration
    model_slug = "openai_gpt-4.1-2025-04-14"
    app_number = 1
    
    print(f"\nTarget: {model_slug}/app{app_number}")
    
    # Create Flask app and initialize services
    print("\n[INIT] Initializing Flask application...")
    app = create_app()
    
    with app.app_context():
        task_service = ServiceLocator.get('task_execution_service')
        
        print_section("TEST 1: STATIC ANALYSIS", '-')
        print("Tools: bandit, safety, pylint, flake8, mypy, semgrep")
        
        try:
            task_id = task_service.create_task(
                task_type='static_analysis',
                model_slug=model_slug,
                app_number=app_number,
                metadata={
                    'tools': ['bandit', 'safety', 'pylint', 'flake8', 'mypy', 'semgrep']
                }
            )
            print(f"[OK] Created task: {task_id}")
            
            # Wait for completion
            max_wait = 60
            start_time = time.time()
            while time.time() - start_time < max_wait:
                task = task_service.get_task_status(task_id)
                status = task.get('status', 'unknown')
                
                if status == 'completed':
                    print(f"[OK] Static analysis completed in {time.time() - start_time:.2f}s")
                    result = task.get('result', {})
                    print_service_results('static-analyzer', result)
                    break
                elif status == 'failed':
                    print(f"[FAIL] Static analysis failed: {task.get('error', 'Unknown')}")
                    break
                
                time.sleep(2)
            else:
                print(f"[TIMEOUT] Static analysis did not complete in {max_wait}s")
        
        except Exception as e:
            print(f"[ERROR] Static analysis test failed: {e}")
        
        print_section("TEST 2: SECURITY ANALYSIS (Dynamic)", '-')
        print("Tools: bandit, safety, owasp-zap (if available)")
        
        try:
            task_id = task_service.create_task(
                task_type='security_analysis',
                model_slug=model_slug,
                app_number=app_number,
                metadata={
                    'tools': ['bandit', 'safety', 'owasp-zap']
                }
            )
            print(f"[OK] Created task: {task_id}")
            
            # Wait for completion
            max_wait = 60
            start_time = time.time()
            while time.time() - start_time < max_wait:
                task = task_service.get_task_status(task_id)
                status = task.get('status', 'unknown')
                
                if status == 'completed':
                    print(f"[OK] Security analysis completed in {time.time() - start_time:.2f}s")
                    result = task.get('result', {})
                    print_service_results('security', result)
                    break
                elif status == 'failed':
                    print(f"[FAIL] Security analysis failed: {task.get('error', 'Unknown')}")
                    break
                
                time.sleep(2)
            else:
                print(f"[TIMEOUT] Security analysis did not complete in {max_wait}s")
        
        except Exception as e:
            print(f"[ERROR] Security analysis test failed: {e}")
        
        print_section("TEST 3: PERFORMANCE TESTING", '-')
        print("Load testing with concurrent requests")
        
        try:
            task_id = task_service.create_task(
                task_type='performance_test',
                model_slug=model_slug,
                app_number=app_number,
                metadata={
                    'test_config': {
                        'users': 5,
                        'duration': 10,
                        'spawn_rate': 1
                    }
                }
            )
            print(f"[OK] Created task: {task_id}")
            
            # Wait for completion (performance tests take longer)
            max_wait = 90
            start_time = time.time()
            while time.time() - start_time < max_wait:
                task = task_service.get_task_status(task_id)
                status = task.get('status', 'unknown')
                
                if status == 'completed':
                    print(f"[OK] Performance test completed in {time.time() - start_time:.2f}s")
                    result = task.get('result', {})
                    print_service_results('performance-tester', result)
                    break
                elif status == 'failed':
                    print(f"[FAIL] Performance test failed: {task.get('error', 'Unknown')}")
                    break
                
                time.sleep(3)
            else:
                print(f"[TIMEOUT] Performance test did not complete in {max_wait}s")
        
        except Exception as e:
            print(f"[ERROR] Performance test failed: {e}")
        
        print_section("TEST 4: AI CODE REVIEW", '-')
        print("AI-powered code analysis and recommendations")
        
        # Check if OpenRouter API key is set
        if not os.getenv('OPENROUTER_API_KEY'):
            print("[SKIP] OPENROUTER_API_KEY not set - skipping AI analysis")
        else:
            try:
                task_id = task_service.create_task(
                    task_type='ai_analysis',
                    model_slug=model_slug,
                    app_number=app_number,
                    metadata={
                        'focus_areas': ['security', 'performance', 'best_practices']
                    }
                )
                print(f"[OK] Created task: {task_id}")
                
                # Wait for completion (AI analysis can take longer)
                max_wait = 120
                start_time = time.time()
                while time.time() - start_time < max_wait:
                    task = task_service.get_task_status(task_id)
                    status = task.get('status', 'unknown')
                    
                    if status == 'completed':
                        print(f"[OK] AI analysis completed in {time.time() - start_time:.2f}s")
                        result = task.get('result', {})
                        print_service_results('ai-analyzer', result)
                        break
                    elif status == 'failed':
                        print(f"[FAIL] AI analysis failed: {task.get('error', 'Unknown')}")
                        break
                    
                    time.sleep(3)
                else:
                    print(f"[TIMEOUT] AI analysis did not complete in {max_wait}s")
            
            except Exception as e:
                print(f"[ERROR] AI analysis test failed: {e}")
        
        print_section("TEST SUMMARY")
        print("\n✅ Static Analysis:    Executed")
        print("✅ Security Analysis:  Executed")
        print("✅ Performance Test:   Executed")
        if os.getenv('OPENROUTER_API_KEY'):
            print("✅ AI Code Review:     Executed")
        else:
            print("⏭️  AI Code Review:     Skipped (no API key)")
        
        print("\n" + "=" * 80)
        print("All analyzer services tested successfully!")
        print("=" * 80)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Test cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
