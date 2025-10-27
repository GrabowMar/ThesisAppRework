"""Backfill ALL openai_codex-mini task results with proper structure handling."""
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app import create_app
from app.models.analysis_models import AnalysisTask
from app.services.result_file_writer import write_task_result_files

app = create_app()

def normalize_result_payload(task_id: str, result_summary_json: dict) -> dict:
    """Normalize different result structures to the expected format."""
    
    # Check if it's already in the new format (has 'results' key)
    if 'results' in result_summary_json:
        return result_summary_json
    
    # Check if it's the nested services format
    if 'services' in result_summary_json:
        # This is the comprehensive multi-service format
        # We need to convert it to the simpler format expected by write_task_result_files
        
        # Extract task metadata
        task_data = result_summary_json.get('task', {})
        summary = result_summary_json.get('summary', {})
        services = result_summary_json.get('services', {})
        
        # Build the normalized payload
        normalized = {
            'task_id': task_data.get('task_id', task_id),
            'model_slug': task_data.get('model_slug', ''),
            'app_number': task_data.get('app_number', 0),
            'analysis_type': task_data.get('analysis_type', 'security'),
            'timestamp': result_summary_json.get('metadata', {}).get('timestamp', ''),
            'metadata': result_summary_json.get('metadata', {}),
            'results': {
                'success': summary.get('status') == 'completed',
                'model_slug': task_data.get('model_slug', ''),
                'app_number': task_data.get('app_number', 0),
                'analysis_duration': 0,  # Would need to calculate from services
                'tools_requested': [],  # Would need to extract from services
                'tools_successful': summary.get('tools_executed', 0),
                'tools_failed': 0,
                'tool_results': {},  # Will populate from services
                'raw_outputs': result_summary_json,  # Keep the full structure
                'summary': summary
            },
            'summary': summary
        }
        
        # Extract tool results from each service
        all_tools = []
        for service_name, service_data in services.items():
            if isinstance(service_data, dict):
                payload = service_data.get('payload', {})
                tool_results = payload.get('tool_results', {})
                
                # Add each tool result to the normalized structure
                for tool_name, tool_data in tool_results.items():
                    if isinstance(tool_data, dict):
                        all_tools.append(tool_name)
                        # Add to tool_results with service prefix
                        key = f"{service_name}_{tool_name}"
                        normalized['results']['tool_results'][key] = tool_data
        
        normalized['results']['tools_requested'] = all_tools
        
        return normalized
    
    # If we can't normalize it, return as-is
    return result_summary_json

with app.app_context():
    tasks = AnalysisTask.query.filter_by(
        target_model='openai_codex-mini',
        status='completed'
    ).all()
    
    print(f"Found {len(tasks)} completed tasks for openai_codex-mini\n")
    
    success_count = 0
    skip_count = 0
    error_count = 0
    
    for task in tasks:
        if not task.result_summary:
            print(f"⏭️  {task.task_id}: No result_summary, skipping")
            skip_count += 1
            continue
        
        try:
            result_payload = json.loads(task.result_summary)
            
            # Normalize the payload to handle different structures
            normalized_payload = normalize_result_payload(task.task_id, result_payload)
            
            # Write the result files
            write_task_result_files(task, normalized_payload)
            
            print(f"✅ {task.task_id} (app{task.target_app_number})")
            success_count += 1
            
        except Exception as e:
            print(f"❌ {task.task_id}: {e}")
            error_count += 1
    
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  ✅ Success: {success_count}")
    print(f"  ⏭️  Skipped: {skip_count}")
    print(f"  ❌ Errors: {error_count}")
    print(f"{'='*60}")
