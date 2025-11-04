"""
Result File Writer
==================

Handles writing analysis result payloads to disk in a standardized format.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from app.models import AnalysisTask
from app.paths import RESULTS_DIR
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

def write_task_result_files(task: AnalysisTask, payload: Dict[str, Any]) -> Optional[Path]:
    """
    Writes result files for a task to a structured directory.

    Args:
        task: The AnalysisTask instance.
        payload: The analysis result payload.

    Returns:
        The path to the main result file if successful, otherwise None.
    """
    try:
        analysis_type = task.task_name
        
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
            return None
        elif findings_count == 0 and not tools_used:
            logger.warning(
                f"Task {task.task_id}: Payload has no findings and no tools_used - "
                f"possible incomplete analysis result. Payload keys: {list(payload.keys())}"
            )

        # Define paths matching analyzer_manager.py structure
        model_slug = task.target_model
        app_number = task.target_app_number
        task_id = task.task_id
        
        # Use task_id directly (it already has "task_" prefix)
        base_dir = RESULTS_DIR / model_slug / f"app{app_number}" / task_id
        base_dir.mkdir(parents=True, exist_ok=True)
        
        # Main result file with timestamp for uniqueness
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = base_dir / f"{model_slug}_app{app_number}_{task_id}_{timestamp}.json"
        
        # Build comprehensive consolidated structure matching analyzer_manager.py
        from datetime import datetime
        
        # Extract service results and build normalized tools map
        services = {}
        tools = {}
        findings = payload.get('findings', [])
        
        # Process service-level results if present
        for service_key in ['static', 'security', 'dynamic', 'performance']:
            if service_key in payload:
                services[service_key] = payload[service_key]
                # Extract tool information from service results
                service_data = payload[service_key]
                if isinstance(service_data, dict) and 'analysis' in service_data:
                    analysis_data = service_data['analysis']
                    if 'tools' in analysis_data:
                        for tool_name, tool_data in analysis_data['tools'].items():
                            if tool_name not in tools:
                                tools[tool_name] = tool_data
        
        # If tools not extracted from services, check top-level payload
        if not tools and 'tools' in payload:
            tools = payload['tools']
        
        # Build severity breakdown from findings
        severity_breakdown = {'high': 0, 'medium': 0, 'low': 0, 'info': 0}
        findings_by_tool = {}
        
        if isinstance(findings, list):
            for finding in findings:
                sev = finding.get('severity', 'info').lower()
                if sev in severity_breakdown:
                    severity_breakdown[sev] += 1
                tool = finding.get('tool', 'unknown')
                findings_by_tool[tool] = findings_by_tool.get(tool, 0) + 1
        
        # Consolidate tool lists
        tools_used = sorted(list(tools.keys()))
        tools_failed = [t for t, info in tools.items() if isinstance(info, dict) and info.get('status') in ['failed', 'error']]
        tools_skipped = [t for t, info in tools.items() if isinstance(info, dict) and info.get('status') in ['skipped', 'not_available']]
        
        # Build final consolidated structure matching analyzer_manager.py format
        consolidated = {
            'metadata': {
                'model_slug': model_slug,
                'app_number': app_number,
                'analysis_type': analysis_type,
                'timestamp': datetime.now().isoformat() + '+00:00',
                'analyzer_version': '1.0.0',
                'module': 'analysis',
                'version': '1.0'
            },
            'results': {
                'task': {
                    'task_id': task_id,
                    'analysis_type': analysis_type,
                    'model_slug': model_slug,
                    'app_number': app_number,
                    'started_at': task.started_at.isoformat() if task.started_at else datetime.now().isoformat(),
                    'completed_at': task.completed_at.isoformat() if task.completed_at else datetime.now().isoformat()
                },
                'summary': {
                    'total_findings': len(findings) if isinstance(findings, list) else 0,
                    'services_executed': len(services),
                    'tools_executed': len(tools),
                    'severity_breakdown': severity_breakdown,
                    'findings_by_tool': findings_by_tool,
                    'tools_used': tools_used,
                    'tools_failed': tools_failed,
                    'tools_skipped': tools_skipped,
                    'status': 'completed'
                },
                'services': services,
                'tools': tools,
                'raw_outputs': payload.get('raw_outputs', {}),
                'findings': findings
            }
        }
        
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(consolidated, f, indent=2, default=str)
            
        logger.info(f"Successfully wrote consolidated result file to {result_file}")
        logger.info(f"[STATS] Saved {len(findings)} findings from {len(tools)} tools for task {task_id}")
        
        # Write manifest.json for task tracking (matching analyzer_manager.py)
        manifest = {
            'task_id': task_id,
            'model_slug': model_slug,
            'app_number': app_number,
            'analysis_type': analysis_type,
            'primary_result': result_file.name,
            'timestamp': timestamp,
            'files': [result_file.name]
        }
        
        manifest_file = base_dir / 'manifest.json'
        with open(manifest_file, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, default=str)
        logger.info(f"Successfully wrote manifest to {manifest_file}")
        
        # Optional: Write SARIF if present
        if 'sarif' in payload and isinstance(payload['sarif'], dict):
            sarif_file = base_dir / "consolidated.sarif.json"
            with open(sarif_file, 'w', encoding='utf-8') as f:
                json.dump(payload['sarif'], f, indent=2, default=str)
            logger.info(f"Successfully wrote SARIF file to {sarif_file}")
            manifest['files'].append(sarif_file.name)

        return result_file

    except Exception as e:
        logger.error(f"Failed to write result files for task {task.task_id}: {e}", exc_info=True)
        return None
