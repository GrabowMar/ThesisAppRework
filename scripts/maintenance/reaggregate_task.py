#!/usr/bin/env python3
"""Re-aggregate analysis results for existing tasks."""
import sys
sys.path.insert(0, 'src')

from app import create_app
from app.models import AnalysisTask
from app.services.task_execution_service import TaskExecutionService

app = create_app()
with app.app_context():
    # Get task execution service
    task_service = TaskExecutionService()
    
    # Find the task
    task_id = 'task_c0e7bdb31730'
    task = AnalysisTask.query.filter_by(task_id=task_id).first()
    if not task:
        print(f"Task {task_id} not found")
        sys.exit(1)
    
    print(f"Re-aggregating results for task: {task_id}")
    print(f"Model: {task.target_model}, App: {task.target_app_number}")
    
    # Get the services data
    result_summary = task.get_result_summary()
    services_block = result_summary.get('services', {})
    
    print(f"\nFound {len(services_block)} services:")
    for svc_name in services_block.keys():
        print(f"  - {svc_name}")
    
    # Extract tool results from each service payload
    all_tool_results = {}
    for service_name, service_data in services_block.items():
        payload = service_data.get('payload', {})
        print(f"\n📦 Extracting from {service_name}...")
        print(f"   Payload keys: {list(payload.keys())}")
        
        # Use the fixed extraction method
        tools = task_service._extract_tool_results_from_payload(service_name, payload)
        print(f"   Found {len(tools)} tools: {list(tools.keys())}")
        
        all_tool_results.update(tools)
    
    print(f"\n" + "="*60)
    print(f"TOTAL TOOLS EXTRACTED: {len(all_tool_results)}")
    print("="*60)
    
    for tool_name, tool_data in all_tool_results.items():
        status = tool_data.get('status', 'unknown')
        executed = tool_data.get('executed', False)
        total_issues = tool_data.get('total_issues', 0)
        emoji = "✅" if status == "success" else "❌" if status == "error" else "⚠️"
        print(f"{emoji} {tool_name:20s} - {status:10s} (executed: {executed}, issues: {total_issues})")
    
    # Now update the result_summary with tool_results at the top level
    result_summary['tool_results'] = all_tool_results
    result_summary['tools'] = all_tool_results  # Also add as 'tools' for compatibility
    
    # Update summary with tools_executed count
    if 'summary' not in result_summary:
        result_summary['summary'] = {}
    result_summary['summary']['tools_executed'] = len([t for t in all_tool_results.values() if t.get('executed')])
    result_summary['summary']['tools_used'] = list(all_tool_results.keys())
    
    # Save back to database
    task.set_result_summary(result_summary)
    from app.extensions import db
    db.session.commit()
    
    print(f"\n✅ Task updated with {len(all_tool_results)} tool results")
