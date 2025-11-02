import pytest

pytestmark = [pytest.mark.integration, pytest.mark.api]

"""Test rebuilt task orchestration"""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app

app = create_app()

with app.app_context():
    from app.services.task_service import AnalysisTaskService
    from app.models import GeneratedApplication
    
    # Check for existing apps
    apps = GeneratedApplication.query.limit(5).all()
    print(f"\n[OK] Found {len(apps)} generated applications in database")
    
    if apps:
        test_app = apps[0]
        print(f"  Testing with: {test_app.model_slug}/app{test_app.app_number}")
        
        # Test 1: Single-service task (should use create_task)
        print("\n[TEST 1] Single-service task (1 tool)...")
        try:
            task1 = AnalysisTaskService.create_task(
                model_slug=test_app.model_slug,
                app_number=test_app.app_number,
                tools=["bandit"],
                priority="normal",
                dispatch=False  # Don't dispatch for test
            )
            print(f"  [OK] Created task {task1.task_id}")
            print(f"    Status: {task1.status.value}")
            print(f"    Tools: {task1.metadata.get('tools')}")
        except Exception as e:
            print(f"  [FAIL] {e}")
        
        # Test 2: Multi-service task (should create subtasks)
        print("\n[TEST 2] Multi-service task (tools from different services)...")
        try:
            task2 = AnalysisTaskService.create_main_task_with_subtasks(
                model_slug=test_app.model_slug,
                app_number=test_app.app_number,
                tools=["bandit", "eslint", "apache-bench"],  # 3 different services
                priority="normal"
            )
            print(f"  [OK] Created main task {task2.task_id}")
            print(f"    Status: {task2.status.value}")
            print(f"    Is main task: {task2.is_main_task}")
            print(f"    Subtasks: {len(task2.subtasks) if task2.subtasks else 0}")
            
            if task2.subtasks:
                for st in task2.subtasks:
                    print(f"      - {st.service_name}: {st.metadata.get('tools')}")
        except Exception as e:
            print(f"  [FAIL] {e}")
            import traceback
            traceback.print_exc()
        
        # Test 3: Profile mode (comprehensive)
        print("\n[TEST 3] Profile-based task (all security tools)...")
        from app.engines.container_tool_registry import get_container_tool_registry
        registry = get_container_tool_registry()
        security_tools = [
            name for name, tool in registry.get_all_tools().items()
            if 'security' in [t.lower() for t in tool.tags] and tool.available
        ]
        print(f"  Found {len(security_tools)} security tools: {security_tools[:5]}...")
        
        if security_tools:
            try:
                task3 = AnalysisTaskService.create_main_task_with_subtasks(
                    model_slug=test_app.model_slug,
                    app_number=test_app.app_number,
                    tools=security_tools,
                    priority="normal"
                )
                print(f"  [OK] Created security analysis task {task3.task_id}")
                print(f"    Subtasks: {len(task3.subtasks) if task3.subtasks else 0}")
                
                # Show grouping
                tools_by_svc = task3.metadata.get('tools_by_service', {})
                for svc, tools in tools_by_svc.items():
                    print(f"      - {svc}: {len(tools)} tools")
            except Exception as e:
                print(f"  [FAIL] {e}")
                import traceback
                traceback.print_exc()
    else:
        print("\n[WARN] No generated applications found in database")
        print("  Run code generation first to create test targets")

print("\n" + "="*60)
print("Task orchestration rebuild complete!")
print("="*60)
