"""
Unified Result Builder
======================

Canonical result structure builder for uniform outputs across all analysis paths:
- API (/api/analysis/run)
- Pipeline (PipelineExecutionService)
- CLI (analyzer_manager.py)

This module ensures all analysis paths produce identical result structures.
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .sarif_utils import extract_sarif_to_files, strip_sarif_rules
from .tool_normalization import (
    SEVERITY_LEVELS,
    aggregate_findings_from_services,
    categorize_services,
    collect_normalized_tools,
    determine_overall_status,
    get_severity_breakdown,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# RESULT SCHEMA VERSION
# ==============================================================================

SCHEMA_VERSION = "2.0"
SCHEMA_NAME = "unified-analysis"


# ==============================================================================
# CANONICAL RESULT STRUCTURE
# ==============================================================================

class UnifiedResultBuilder:
    """Builds canonical result structure from service outputs.
    
    Result Structure (v2.0):
    {
        "schema": {"name": "unified-analysis", "version": "2.0"},
        "metadata": {
            "task_id": str,
            "model_slug": str,
            "app_number": int,
            "analysis_type": str,
            "timestamp": str (ISO8601),
            "duration_seconds": float,
            "analyzer_version": str
        },
        "summary": {
            "status": str,
            "total_findings": int,
            "severity_breakdown": {"critical": int, "high": int, ...},
            "services_executed": int,
            "services_unreachable": int,
            "services_partial": int,
            "tools_executed": int,
            "tools_used": [str],
            "tools_failed": [str],
            "tools_skipped": [str]
        },
        "tools": {
            "<tool_name>": {
                "status": str,
                "service": str,
                "findings_count": int,
                "execution_time": float?,
                "sarif_file": str?,
                "severity_breakdown": {...}?
            }
        },
        "services": {
            "<service_name>": { ... raw service output ... }
        }
    }
    """
    
    def __init__(
        self,
        task_id: str,
        model_slug: str,
        app_number: int,
        analysis_type: str = "comprehensive",
        start_time: Optional[float] = None
    ):
        """Initialize builder with task metadata.
        
        Args:
            task_id: Unique task identifier
            model_slug: Model identifier (e.g., 'openai_gpt-4')
            app_number: Application number
            analysis_type: Type of analysis ('comprehensive', 'static', etc.)
            start_time: Analysis start timestamp (defaults to now)
        """
        self.task_id = task_id
        self.model_slug = model_slug
        self.app_number = app_number
        self.analysis_type = analysis_type
        self.start_time = start_time or time.time()
        
        # State
        self._services: Dict[str, Any] = {}
        self._tools_requested: Set[str] = set()
        self._detected_languages: List[str] = []
        
    def add_service_result(self, service_name: str, result: Dict[str, Any]) -> 'UnifiedResultBuilder':
        """Add a service's result to the builder.
        
        Args:
            service_name: Name of service (e.g., 'static', 'dynamic')
            result: Raw service output
            
        Returns:
            self for chaining
        """
        self._services[service_name] = result
        return self
        
    def set_tools_requested(self, tools: List[str]) -> 'UnifiedResultBuilder':
        """Set list of tools that were requested for analysis.
        
        Args:
            tools: List of tool names
            
        Returns:
            self for chaining
        """
        self._tools_requested = set(tools)
        return self
        
    def set_detected_languages(self, languages: List[str]) -> 'UnifiedResultBuilder':
        """Set detected programming languages.
        
        Args:
            languages: List of language names
            
        Returns:
            self for chaining
        """
        self._detected_languages = languages
        return self
        
    def build(self, end_time: Optional[float] = None) -> Dict[str, Any]:
        """Build the canonical result structure.
        
        Args:
            end_time: Analysis end timestamp (defaults to now)
            
        Returns:
            Canonical result dictionary
        """
        end_time = end_time or time.time()
        duration = max(0.0, end_time - self.start_time)
        
        # Aggregate findings from all services
        aggregated = aggregate_findings_from_services(self._services)
        
        # Collect normalized tools
        normalized_tools = collect_normalized_tools(self._services)
        
        # Categorize services
        succeeded, partial, unreachable = categorize_services(self._services)
        
        # Determine overall status
        overall_status = determine_overall_status(succeeded, partial, unreachable)
        
        # Calculate tool status lists
        tools_failed = []
        tools_skipped = []
        for tname, tinfo in normalized_tools.items():
            status = str(tinfo.get('status', 'unknown')).lower()
            if status in ('skipped', 'not_available'):
                tools_skipped.append(tname)
            elif status not in ('success', 'completed', 'no_issues'):
                tools_failed.append(tname)
        
        # All tools used (from normalized + aggregated)
        all_tools = sorted(set(normalized_tools.keys()) | set(aggregated.get('tools_executed', [])))
        
        result = {
            'schema': {
                'name': SCHEMA_NAME,
                'version': SCHEMA_VERSION
            },
            'metadata': {
                'task_id': self.task_id,
                'model_slug': self.model_slug,
                'app_number': self.app_number,
                'analysis_type': self.analysis_type,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'duration_seconds': round(duration, 2),
                'analyzer_version': '1.0.0',
                'languages_detected': self._detected_languages
            },
            'summary': {
                'status': overall_status,
                'total_findings': aggregated.get('findings_total', 0),
                'severity_breakdown': aggregated.get('findings_by_severity', {}),
                'findings_by_tool': aggregated.get('findings_by_tool', {}),
                'services_executed': len(succeeded),
                'services_unreachable': len(unreachable),
                'services_partial': len(partial),
                'tools_executed': len(normalized_tools),
                'tools_used': all_tools,
                'tools_failed': sorted(tools_failed),
                'tools_skipped': sorted(tools_skipped)
            },
            'tools': normalized_tools,
            'services': self._order_services(self._services)
        }
        
        return result
    
    def build_and_save(
        self,
        output_dir: Path,
        end_time: Optional[float] = None,
        extract_sarif: bool = True
    ) -> Path:
        """Build result and save to filesystem.
        
        Args:
            output_dir: Directory to save results
            end_time: Analysis end timestamp
            extract_sarif: Whether to extract SARIF to separate files
            
        Returns:
            Path to saved result file
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Extract SARIF if requested
        if extract_sarif:
            sarif_dir = output_dir / 'sarif'
            sarif_dir.mkdir(exist_ok=True)
            self._services = extract_sarif_to_files(self._services, sarif_dir)
        
        # Build result
        result = self.build(end_time)
        
        # Generate filename
        safe_slug = self.model_slug.replace('/', '_').replace('\\', '_')
        sanitized_task = self._sanitize_task_id(self.task_id)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Ensure task prefix consistency
        task_part = sanitized_task if sanitized_task.startswith('task_') else f"task_{sanitized_task}"
        filename = f"{safe_slug}_app{self.app_number}_{task_part}_{timestamp}.json"
        filepath = output_dir / filename
        
        # Write result
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, default=str)
        
        logger.info(f"[SAVE] Results saved to: {filepath}")
        
        # Write service snapshots
        self._write_service_snapshots(output_dir, safe_slug, result)
        
        # Write manifest
        self._write_manifest(output_dir, filename, result)
        
        return filepath
    
    def _order_services(self, services: Dict[str, Any]) -> Dict[str, Any]:
        """Order services in preferred display order."""
        preferred = ['static', 'security', 'dynamic', 'performance', 'ai']
        ordered = {}
        
        # Add preferred first
        for key in preferred:
            if key in services:
                ordered[key] = services[key]
        
        # Add remaining alphabetically
        for key in sorted(k for k in services.keys() if k not in ordered):
            ordered[key] = services[key]
        
        return ordered
    
    def _sanitize_task_id(self, task_id: str) -> str:
        """Sanitize task ID for filesystem use."""
        return ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in str(task_id))
    
    def _write_service_snapshots(
        self,
        output_dir: Path,
        safe_slug: str,
        result: Dict[str, Any]
    ) -> None:
        """Write per-service JSON snapshots."""
        services_dir = output_dir / 'services'
        services_dir.mkdir(exist_ok=True)
        
        services = result.get('services', {})
        metadata = result.get('metadata', {})
        
        for service_name, payload in services.items():
            if not isinstance(payload, dict):
                continue
            
            snapshot = {
                'metadata': {
                    'model_slug': metadata.get('model_slug'),
                    'app_number': metadata.get('app_number'),
                    'task_id': metadata.get('task_id'),
                    'service_name': service_name,
                    'created_at': datetime.now(timezone.utc).isoformat()
                },
                'results': payload
            }
            
            filename = f"{safe_slug}_app{metadata.get('app_number', 0)}_{service_name}.json"
            filepath = services_dir / filename
            
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(snapshot, f, indent=2, default=str)
            except Exception as e:
                logger.debug(f"Failed to write {service_name} snapshot: {e}")
    
    def _write_manifest(
        self,
        output_dir: Path,
        primary_filename: str,
        result: Dict[str, Any]
    ) -> None:
        """Write task manifest file."""
        services_dir = output_dir / 'services'
        service_files = {}
        
        if services_dir.exists():
            for service_path in services_dir.glob('*.json'):
                key = service_path.stem.split('_')[-1]
                service_files[key] = service_path.name
        
        metadata = result.get('metadata', {})
        services = result.get('services', {})
        
        manifest = {
            'task_id': metadata.get('task_id'),
            'model_slug': metadata.get('model_slug'),
            'app_number': metadata.get('app_number'),
            'analysis_type': metadata.get('analysis_type'),
            'schema_version': SCHEMA_VERSION,
            'primary_result': primary_filename,
            'services': sorted(services.keys()),
            'service_files': service_files,
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        try:
            with open(output_dir / 'manifest.json', 'w', encoding='utf-8') as f:
                json.dump(manifest, f, indent=2, default=str)
        except Exception as e:
            logger.debug(f"Failed to write manifest: {e}")


# ==============================================================================
# CONVENIENCE FUNCTIONS
# ==============================================================================

def build_result_from_services(
    task_id: str,
    model_slug: str,
    app_number: int,
    services: Dict[str, Any],
    analysis_type: str = "comprehensive",
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
    tools_requested: Optional[List[str]] = None,
    detected_languages: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Build canonical result from service outputs.
    
    Convenience function wrapping UnifiedResultBuilder.
    
    Args:
        task_id: Unique task identifier
        model_slug: Model identifier
        app_number: Application number
        services: Dict of {service_name: service_result}
        analysis_type: Type of analysis
        start_time: Start timestamp
        end_time: End timestamp
        tools_requested: List of requested tools
        detected_languages: Detected languages
        
    Returns:
        Canonical result dictionary
    """
    builder = UnifiedResultBuilder(
        task_id=task_id,
        model_slug=model_slug,
        app_number=app_number,
        analysis_type=analysis_type,
        start_time=start_time
    )
    
    for service_name, result in services.items():
        builder.add_service_result(service_name, result)
    
    if tools_requested:
        builder.set_tools_requested(tools_requested)
    
    if detected_languages:
        builder.set_detected_languages(detected_languages)
    
    return builder.build(end_time)


def save_result_to_filesystem(
    task_id: str,
    model_slug: str,
    app_number: int,
    services: Dict[str, Any],
    results_dir: Path,
    analysis_type: str = "comprehensive",
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
    tools_requested: Optional[List[str]] = None,
    detected_languages: Optional[List[str]] = None,
    extract_sarif: bool = True
) -> Path:
    """Build and save canonical result to filesystem.
    
    Creates directory structure:
    {results_dir}/{model_slug}/app{N}/task_{task_id}/
        ├── {model}_app{N}_task_{id}_{timestamp}.json
        ├── manifest.json
        ├── sarif/
        │   └── *.sarif.json
        └── services/
            └── *.json
    
    Args:
        task_id: Unique task identifier
        model_slug: Model identifier
        app_number: Application number
        services: Dict of {service_name: service_result}
        results_dir: Base results directory
        analysis_type: Type of analysis
        start_time: Start timestamp
        end_time: End timestamp
        tools_requested: List of requested tools
        detected_languages: Detected languages
        extract_sarif: Extract SARIF to separate files
        
    Returns:
        Path to saved result file
    """
    safe_slug = model_slug.replace('/', '_').replace('\\', '_')
    sanitized_task = ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in str(task_id))
    
    # Build output directory path
    task_dir_name = sanitized_task if sanitized_task.startswith('task_') else f"task_{sanitized_task}"
    output_dir = results_dir / safe_slug / f"app{app_number}" / task_dir_name
    
    builder = UnifiedResultBuilder(
        task_id=task_id,
        model_slug=model_slug,
        app_number=app_number,
        analysis_type=analysis_type,
        start_time=start_time
    )
    
    for service_name, result in services.items():
        builder.add_service_result(service_name, result)
    
    if tools_requested:
        builder.set_tools_requested(tools_requested)
    
    if detected_languages:
        builder.set_detected_languages(detected_languages)
    
    return builder.build_and_save(output_dir, end_time, extract_sarif)


# ==============================================================================
# UNIVERSAL FORMAT BRIDGE
# ==============================================================================

def build_universal_format(
    task_id: str,
    model_slug: str,
    app_number: int,
    services: Dict[str, Any],
    start_time: float,
    end_time: float,
    tools_requested: Optional[List[str]] = None,
    detected_languages: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Build universal-v1 format result (for backward compatibility).
    
    This format is simpler and focuses on tool-level results only.
    Used by CLI when UNIVERSAL_RESULTS=1 is set.
    
    Args:
        task_id: Unique task identifier
        model_slug: Model identifier
        app_number: Application number
        services: Dict of {service_name: service_result}
        start_time: Start timestamp
        end_time: End timestamp
        tools_requested: List of requested tools
        detected_languages: Detected languages
        
    Returns:
        Universal-v1 format dictionary
    """
    import os
    
    max_len = int(os.getenv('UNIVERSAL_RAW_MAX', '16000'))
    include_stderr = os.getenv('UNIVERSAL_INCLUDE_STDERR', '1') not in ('0', 'false', 'False')
    
    # Collect normalized tools
    normalized_tools = collect_normalized_tools(services)
    
    # Build universal tool records
    tools_map = {}
    success_count = 0
    failed_count = 0
    
    for name, data in sorted(normalized_tools.items()):
        status = str(data.get('status', 'unknown'))
        
        if status in ('error', 'failed', 'not_available'):
            failed_count += 1
        elif status not in ('skipped', 'not_available'):
            success_count += 1
        
        # Build raw block
        raw_block = {}
        if isinstance(data.get('raw_output'), str) and data['raw_output'].strip():
            raw_block['stdout'] = _truncate(data['raw_output'], max_len)
        if include_stderr and isinstance(data.get('error'), str) and data['error'].strip():
            raw_block['stderr'] = _truncate(data['error'], max_len)
        
        tools_map[name] = {
            k: v for k, v in {
                'status': status,
                'duration_seconds': data.get('execution_time'),
                'issue_count': data.get('findings_count'),
                'severity_breakdown': data.get('severity_breakdown'),
                'raw': raw_block or None
            }.items() if v is not None and v != {} and v != ''
        }
    
    # Calculate overall status
    if failed_count > 0 and success_count == 0:
        overall_status = 'failed'
    elif failed_count > 0:
        overall_status = 'partial'
    else:
        overall_status = 'completed'
    
    # Determine all tools used
    all_tools = tools_requested or list(normalized_tools.keys())
    
    return {
        'schema': {'name': 'universal', 'version': 'v1'},
        'metadata': {
            'task_id': task_id,
            'model_slug': model_slug,
            'app_number': app_number,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'duration_seconds': max(0.0, end_time - start_time),
            'tools_requested': sorted(all_tools),
            'tools_successful': success_count,
            'tools_failed': failed_count,
            'status': overall_status,
            'languages_detected': detected_languages or []
        },
        'tools': tools_map
    }


def _truncate(value: str, limit: int) -> str:
    """Truncate string with indicator."""
    if len(value) <= limit:
        return value
    return value[:limit] + f"\n...<truncated {len(value)-limit} chars>"


# ==============================================================================
# RESULT LOADING & VALIDATION
# ==============================================================================

def load_result_file(filepath: Path) -> Dict[str, Any]:
    """Load and validate a result file.
    
    Args:
        filepath: Path to result JSON file
        
    Returns:
        Loaded result dictionary
        
    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is invalid JSON
        ValueError: If file doesn't match expected schema
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Validate structure
    if not isinstance(data, dict):
        raise ValueError("Result file must be a JSON object")
    
    # Check for schema info (v2.0+)
    if 'schema' in data:
        schema = data['schema']
        if schema.get('name') not in (SCHEMA_NAME, 'universal'):
            logger.warning(f"Unknown schema: {schema}")
    
    return data


def get_result_summary(result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract summary from result regardless of format version.
    
    Args:
        result: Loaded result dictionary
        
    Returns:
        Summary dictionary with standardized keys
    """
    # Try v2.0 structure first
    if 'summary' in result:
        return result['summary']
    
    return {}
