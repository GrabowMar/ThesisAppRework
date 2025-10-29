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

        # Define paths
        model_slug = task.target_model
        app_number = task.target_app_number
        task_id = task.task_id
        
        base_dir = RESULTS_DIR / model_slug / f"app{app_number}" / "analysis" / task_id
        base_dir.mkdir(parents=True, exist_ok=True)
        
        # Main result file
        result_file = base_dir / "consolidated.json"
        
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, default=str)
            
        logger.info(f"Successfully wrote main result file to {result_file}")
        
        # Optional: Write SARIF if present
        if 'sarif' in payload and isinstance(payload['sarif'], dict):
            sarif_file = base_dir / "consolidated.sarif.json"
            with open(sarif_file, 'w', encoding='utf-8') as f:
                json.dump(payload['sarif'], f, indent=2, default=str)
            logger.info(f"Successfully wrote SARIF file to {sarif_file}")

        return result_file

    except Exception as e:
        logger.error(f"Failed to write result files for task {task.task_id}: {e}", exc_info=True)
        return None
