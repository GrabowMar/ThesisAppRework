"""Helper for writing analysis result files to disk.

This module ensures that analysis results are persisted both to the database
AND to disk files, maintaining compatibility with the ResultFileService that
the UI uses to display results.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from app.models import AnalysisTask
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


def _normalize_payload_structure(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize different payload structures to extract all tool results.
    
    Handles two structures:
    1. Simple: {'results': {'tool_results': {...}}}
    2. Nested: {'services': {'SERVICE': {'payload': {'tool_results': {...}}}}}
    
    Returns:
        Normalized structure with all tool results in flat tool_results dict
    """
    if isinstance(payload.get('tool_results'), dict) and payload['tool_results']:
        normalized = dict(payload)
        if not isinstance(normalized.get('summary'), dict):
            normalized['summary'] = {}
        return normalized

    # Check if it's already a simple results structure
    if 'results' in payload and isinstance(payload.get('results'), dict):
        results = payload['results']
        # If tool_results already exists and has data, return as-is
        if results.get('tool_results') and isinstance(results['tool_results'], dict):
            if len(results['tool_results']) > 0:
                return payload.get('payload', payload)
    
    # Check for nested services structure
    if 'services' in payload and isinstance(payload.get('services'), dict):
        services = payload['services']
        
        # Extract all tool results from all services
        all_tool_results = {}
        all_tools_used = []
        total_findings = 0
        services_executed = 0
        
        for service_name, service_data in services.items():
            if not isinstance(service_data, dict):
                continue
                
            services_executed += 1
            # Service data might be nested under 'payload' or be the payload itself
            service_payload = service_data.get('payload', service_data)
            
            if not isinstance(service_payload, dict):
                continue
                
            tool_results = service_payload.get('tool_results', {})
            
            if not isinstance(tool_results, dict):
                continue
            
            # Add each tool result with service prefix to avoid collisions
            for tool_name, tool_data in tool_results.items():
                prefixed_key = f"{service_name}_{tool_name}"
                all_tool_results[prefixed_key] = tool_data
                all_tools_used.append(tool_name)
                
                # Count findings if present
                if isinstance(tool_data, dict):
                    findings_count = tool_data.get('total_issues', 0) or tool_data.get('issues_found', 0)
                    if findings_count:
                        total_findings += findings_count
        
        # Build normalized structure
        normalized = {
            'success': True,
            'model_slug': payload.get('task', {}).get('model_slug', ''),
            'app_number': payload.get('task', {}).get('app_number', 0),
            'analysis_duration': 0,
            'tools_requested': all_tools_used,
            'tools_successful': len(all_tool_results),
            'tools_failed': 0,
            'tool_results': all_tool_results,
            'raw_outputs': payload,  # Preserve original structure
            'summary': {
                'total_findings': total_findings,
                'services_executed': services_executed,
                'tools_executed': len(all_tool_results),
                'status': 'completed'
            },
            'findings': payload.get('findings', [])
        }
        
        return normalized
    
    # If we can't normalize, return the payload or nested payload
    return payload.get('payload', payload)


def write_task_result_files(task: AnalysisTask, payload: Dict[str, Any]) -> Optional[Path]:
    """Write analysis result files to disk for a completed task.
    
    Creates:
    - Main result JSON file
    - Manifest JSON file
    
    Args:
        task: The AnalysisTask instance
        payload: The analysis payload to write
        
    Returns:
        Path to the main result file, or None if write failed
    """
    # Log the write attempt with summary metrics
    analysis_type = task.analysis_type.value if hasattr(task.analysis_type, 'value') else str(task.analysis_type)
    findings_count = len(payload.get('findings', [])) if isinstance(payload.get('findings'), list) else 0
    tools_used = payload.get('tools_used', []) if isinstance(payload.get('tools_used'), list) else []
    
    logger.info(
        f"Writing result files for task {task.task_id}: "
        f"model={task.target_model} app={task.target_app_number} "
        f"type={analysis_type} findings={findings_count} tools={len(tools_used)}"
    )
    
    # Warn if payload appears empty or incomplete
    if not payload:
        logger.warning(f"Task {task.task_id}: Received empty payload for file write")
    elif findings_count == 0 and len(tools_used) == 0:
        logger.warning(
            f"Task {task.task_id}: Payload has no findings and no tools_used - "
            f"possible incomplete analysis result. Payload keys: {list(payload.keys())}"
        )
    
    try:
        # Get project root
        project_root = Path(__file__).resolve().parents[3]
        
        # Create results directory structure
        model_safe = task.target_model.replace('/', '_').replace('\\', '_')
        results_dir = project_root / 'results' / model_safe / f'app{task.target_app_number}'
        
        # Create task-specific directory with task_id and timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        analysis_type = task.analysis_type.value if hasattr(task.analysis_type, 'value') else str(task.analysis_type)
        # Include task_id to prevent collisions from same-second completions
        task_dir = results_dir / f'task_{analysis_type}_{task.task_id}_{timestamp}'
        task_dir.mkdir(parents=True, exist_ok=True)
        
        # Write main result file with task_id
        filename = f'{model_safe}_app{task.target_app_number}_task_{analysis_type}_{task.task_id}_{timestamp}.json'
        filepath = task_dir / filename
        
        # Normalize and wrap payload in standard format with metadata
        normalized_results = _normalize_payload_structure(payload)
        
        wrapped_payload = {
            'task_id': task.task_id,
            'model_slug': task.target_model,
            'app_number': task.target_app_number,
            'analysis_type': analysis_type,
            'timestamp': datetime.now().isoformat() + '+00:00',
            'metadata': {
                'task_id': task.task_id,
                'model_slug': task.target_model,
                'app_number': task.target_app_number,
                'analysis_type': analysis_type,
                'timestamp': datetime.now().isoformat() + '+00:00',
                'analyzer_version': '1.0.0',
                'module': analysis_type,
                'version': '1.0'
            },
            'results': normalized_results,
            'summary': normalized_results.get('summary', {}),
        }
        
        # Write main result file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(wrapped_payload, f, indent=2, default=str)
        
        logger.info(f"Wrote result file: {filepath}")
        
        # Write manifest
        manifest_path = task_dir / 'manifest.json'
        manifest = {
            'task_id': task.task_id,
            'model_slug': task.target_model,
            'app_number': task.target_app_number,
            'primary_result': filename,
            'services': [],
            'service_files': {},
            'created_at': datetime.now().isoformat() + '+00:00'
        }
        
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)
        
        logger.debug(f"Wrote manifest: {manifest_path}")
        
        return filepath
        
    except Exception as e:
        logger.warning(f"Failed to write result files for task {task.task_id}: {e}")
        return None


def write_task_result_files_by_id(task_id: str, payload: Dict[str, Any]) -> bool:
    """Write result files by task ID.
    
    Args:
        task_id: The task ID to look up
        payload: The analysis payload to write
        
    Returns:
        True if files were written successfully, False otherwise
    """
    task = AnalysisTask.query.filter_by(task_id=task_id).first()
    if not task:
        logger.warning(f"Cannot write result files: task {task_id} not found")
        return False
    
    result = write_task_result_files(task, payload)
    return result is not None
