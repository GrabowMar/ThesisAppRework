"""
JSON Report Renderer

Generates JSON reports with structured data.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


def render_json(report, data: Dict[str, Any], output_path: Path) -> None:
    """
    Render report as JSON file.
    
    Args:
        report: Report model instance
        data: Report data dictionary
        output_path: Path where JSON file should be saved
    """
    try:
        # Create structured JSON output
        output = {
            'report_metadata': {
                'report_id': report.report_id,
                'report_type': report.report_type,
                'title': report.title,
                'description': report.description,
                'generated_at': data.get('timestamp'),
                'format': 'json'
            },
            'data': data
        }
        
        # Write to file with pretty printing
        with output_path.open('w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, default=_json_serializer)
        
        logger.info(f"Rendered JSON report to {output_path}")
        
    except Exception as e:
        logger.error(f"Error rendering JSON report: {e}", exc_info=True)
        raise


def _json_serializer(obj):
    """Custom JSON serializer for objects not serializable by default json code."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"Type {type(obj)} not serializable")
