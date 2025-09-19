#!/usr/bin/env python3
"""
Debug the orchestrator to see why tools aren't being delegated.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import logging
from app.factory import create_app
from app.services.task_service import AnalysisTaskService
from app.services.task_execution_service import TaskExecutionService

# Enable debug logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def debug_orchestrator():
    app = create_app()
    
    with app.app_context():
        print('🔍 Testing orchestrator with debug logging...')
        
        # Create a task with tool IDs
        task = AnalysisTaskService.create_task(
            model_slug='nousresearch_hermes-4-405b',
            app_number=1,
            analysis_type='performance',
            priority='normal',
            custom_options={
                'selected_tools': [11, 12],  # locust and ab
                'source': 'debug_test'
            }
        )
        print(f'Created task: {task.task_id}')
        
        # Execute it with detailed logging
        executor = TaskExecutionService(app=app)
        result = executor._execute_real_analysis(task)
        
        print(f'Result status: {result.get("status")}')
        if result.get('error'):
            print(f'Error: {result["error"]}')
        
        payload = result.get('payload', {})
        print(f'Tools requested: {payload.get("tools_requested", [])}')
        print(f'Tools successful: {payload.get("tools_successful", 0)}')
        print(f'Tool results keys: {list(payload.get("tool_results", {}).keys())}')
        
        return payload.get("tools_successful", 0) > 0

if __name__ == "__main__":
    success = debug_orchestrator()
    print("✅ Tools executed!" if success else "❌ Tools NOT executed!")