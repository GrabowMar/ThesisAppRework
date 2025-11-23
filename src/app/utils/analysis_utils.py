"""
Analysis Utilities
==================

Shared utilities for analysis path resolution and SARIF processing.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.paths import RESULTS_DIR, PROJECT_ROOT

logger = logging.getLogger(__name__)

def normalize_task_folder_name(result_id: str) -> str:
    """Ensure task folders always start with 'task_' prefix."""
    if not result_id:
        return 'task_unknown'
    return result_id if result_id.startswith('task_') else f'task_{result_id}'


def extract_model_app_from_result(result_data: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """Best-effort extraction of model slug and app number from result payload."""
    model_slug = None
    app_number = None

    metadata = result_data.get('metadata') or {}
    model_slug = metadata.get('model_slug') or metadata.get('model')
    app_number = metadata.get('app_number') or metadata.get('app')

    if not model_slug or not app_number:
        summary = result_data.get('summary') or {}
        model_slug = model_slug or summary.get('model_slug')
        app_number = app_number or summary.get('app_number')

    if not model_slug or not app_number:
        static_analysis = (result_data.get('results') or {}).get('static', {}).get('analysis', {})
        model_slug = model_slug or static_analysis.get('model_slug') or static_analysis.get('target_model')
        app_number = app_number or static_analysis.get('app_number') or static_analysis.get('target_app_number')

    return model_slug, app_number


def resolve_task_directory(result_data: Dict[str, Any], result_id: str) -> Optional[Path]:
    """Resolve the filesystem path for a task's result directory."""
    model_slug, app_number = extract_model_app_from_result(result_data)
    task_folder = normalize_task_folder_name(str(result_id))

    if model_slug and app_number:
        safe_slug = str(model_slug).replace('/', '_')
        return RESULTS_DIR / safe_slug / f'app{app_number}' / task_folder

    results_path = result_data.get('results_path')
    if isinstance(results_path, str) and results_path:
        candidate = Path(results_path)
        if not candidate.is_absolute():
            candidate = (PROJECT_ROOT / candidate).resolve()
        return candidate

    return None


def extract_issues_from_sarif(sarif_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalize SARIF run data into the issue format expected by the UI."""
    extracted_issues = []
    if not isinstance(sarif_data, dict):
        return extracted_issues

    level_map = {
        'error': 'HIGH',
        'warning': 'MEDIUM',
        'note': 'LOW',
        'none': 'INFO'
    }

    for run in sarif_data.get('runs', []):
        rules_index = {}
        driver = (run.get('tool') or {}).get('driver') or {}
        for rule in driver.get('rules', []) or []:
            if isinstance(rule, dict) and rule.get('id'):
                rules_index[rule['id']] = rule

        for result_item in run.get('results', []) or []:
            if not isinstance(result_item, dict):
                continue

            rule_id = result_item.get('ruleId') or result_item.get('rule', {}).get('id')
            message = (result_item.get('message') or {}).get('text') or ''
            level = (result_item.get('level') or 'warning').lower()
            severity = level_map.get(level, 'MEDIUM')

            issue: Dict[str, Any] = {
                'rule': rule_id,
                'rule_id': rule_id,
                'level': level,
                'severity': severity,
                'issue_severity': (result_item.get('properties', {}).get('issue_severity') or severity).upper(),
                'message': message,
                'tool': driver.get('name') or 'SARIF tool'
            }

            locations = result_item.get('locations') or []
            if locations:
                physical_loc = (locations[0] or {}).get('physicalLocation') or {}
                artifact_loc = physical_loc.get('artifactLocation') or {}
                region = physical_loc.get('region') or {}

                uri = artifact_loc.get('uri') or ''
                issue['file'] = uri.replace('file://', '')
                issue['line'] = region.get('startLine')
                issue['column'] = region.get('startColumn')

            properties = result_item.get('properties') or {}
            if 'issue_confidence' in properties:
                issue['confidence'] = properties['issue_confidence']
            if 'issue_severity' in properties:
                issue['issue_severity'] = properties['issue_severity'].upper()
            if 'cwe' in properties:
                issue['cwe'] = properties['cwe']

            if rule_id and rule_id in rules_index:
                rule_meta = rules_index[rule_id]
                if rule_meta.get('helpUri'):
                    issue['help_url'] = rule_meta['helpUri']
                if rule_meta.get('name'):
                    issue['rule_name'] = rule_meta['name']

            extracted_issues.append(issue)

    return extracted_issues
