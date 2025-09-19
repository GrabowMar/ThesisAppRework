#!/usr/bin/env python3
"""
Test the web UI flow for performance analysis.
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app.factory import create_app
from app.services.service_locator import ServiceLocator
from app.services.task_service import AnalysisTaskService
from app.services.task_execution_service import TaskExecutionService

def test_web_ui_flow():
    """Test the same flow that the web UI uses."""
    app = create_app()
    
    with app.app_context():
        print("🔍 Testing web UI performance analysis flow...")
        
        # Step 1: Get tool service and find performance tools
        tool_service = ServiceLocator.get_tool_registry_service()
        if not tool_service:
            print("❌ No tool service available")
            return False
            
        tools = tool_service.get_all_tools()
        perf_tools = [t for t in tools if 'performance' in str(t.get('category', '')).lower()]
        print(f"📋 Found {len(perf_tools)} performance tools:")
        for tool in perf_tools:
            print(f"   ID: {tool.get('id')}, Name: {tool.get('name')}")
        
        if not perf_tools:
            print("❌ No performance tools found")
            return False
            
        # Step 2: Create a task with tool IDs (like the web UI does)
        selected_tool_ids = [t['id'] for t in perf_tools]  # Use tool IDs like web UI
        print(f"🎯 Creating task with tool IDs: {selected_tool_ids}")
        
        try:
            task = AnalysisTaskService.create_task(
                model_slug='nousresearch_hermes-4-405b',
                app_number=1,
                analysis_type='performance',
                priority='normal',
                custom_options={
                    'selected_tools': selected_tool_ids,
                    'source': 'ui_test'
                }
            )
            print(f"✅ Created task: {task.task_id}")
            
            # Step 3: Execute the task using TaskExecutionService
            executor = TaskExecutionService(app=app)
            print("🚀 Executing task...")
            
            # First let's check what the task metadata contains
            print("🔍 Task metadata:")
            try:
                meta = task.get_metadata()
                print(f"   Full metadata: {meta}")
                custom_options = meta.get('custom_options', {})
                print(f"   Custom options: {custom_options}")
                selected_tools = custom_options.get('selected_tools', [])
                print(f"   Selected tools from metadata: {selected_tools}")
            except Exception as e:
                print(f"   Error getting metadata: {e}")
            
            result = executor._execute_real_analysis(task)
            print(f"📊 Task result: {result.get('status')}")
            
            if result.get('error'):
                print(f"❌ Error: {result['error']}")
                return False
            
            if result.get('payload'):
                payload = result['payload']
                print(f"📋 Full payload keys: {list(payload.keys())}")
                
                # Check orchestrator-style keys
                tools_requested = payload.get('tools_requested', [])
                tools_successful = payload.get('tools_successful', [])
                tools_failed = payload.get('tools_failed', [])
                tool_results = payload.get('tool_results', {})
                print(f"🔧 Tools requested: {tools_requested}")
                print(f"✅ Tools successful: {tools_successful}")
                print(f"❌ Tools failed: {tools_failed}")
                print(f"📊 Tool results keys: {list(tool_results.keys())}")
                
                # Check legacy tools_used (should be empty for orchestrator)
                tools_used = payload.get('tools_used', [])
                print(f"🎉 Legacy tools_used: {tools_used}")
                
                # Check if we got results
                results = payload.get('results', {})
                print(f"📈 Results keys: {list(results.keys())}")
                for url, url_results in results.items():
                    print(f"📈 Results for {url}:")
                    for tool_name, tool_result in url_results.items():
                        if isinstance(tool_result, dict):
                            status = tool_result.get('status', 'unknown')
                            print(f"   {tool_name}: {status}")
                
                # Success if any tools were requested and ran
                return len(tools_requested) > 0 and (len(tools_successful) > 0 or len(tool_results) > 0)
            else:
                print("⚠️ No results payload")
                return False
                
        except Exception as e:
            print(f"❌ Error creating/executing task: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = test_web_ui_flow()
    print("✅ Test passed!" if success else "❌ Test failed!")