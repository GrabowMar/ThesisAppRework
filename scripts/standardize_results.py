#!/usr/bin/env python3
"""
Standardize and Consolidate Results
====================================

This script:
1. Normalizes service file naming to canonical format (static.json, dynamic.json, etc.)
2. Removes duplicate files (keeps largest/most complete version)
3. Generates consolidated.json for all task directories
4. Identifies the best task per model/app combination

Usage:
    python3 scripts/standardize_results.py --dry-run   # Preview changes
    python3 scripts/standardize_results.py              # Apply changes
"""
import json
import os
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

RESULTS_DIR = Path(__file__).parent.parent / 'results'

# Canonical service names
CANONICAL_SERVICES = {'static', 'dynamic', 'performance', 'ai'}

# Map various naming conventions to canonical names
NAME_MAP = {
    'static-analyzer': 'static',
    'dynamic-analyzer': 'dynamic',
    'performance-tester': 'performance',
    'ai-analyzer': 'ai',
}

EXPECTED_PYTHON_TOOLS = {
    'bandit', 'pylint', 'semgrep', 'mypy', 'safety',
    'pip-audit', 'vulture', 'ruff', 'radon', 'detect-secrets'
}
EXPECTED_JS_TOOLS = {'eslint', 'npm-audit'}


def classify_service_file(filename: str) -> Optional[str]:
    """Classify a service file to its canonical service name."""
    name = filename.lower()
    if '.old' in name or name.startswith('.'):
        return None
    for pattern, canonical in NAME_MAP.items():
        if pattern in name:
            return canonical
    for svc in CANONICAL_SERVICES:
        if f'_{svc}.json' in name or name == f'{svc}.json':
            return svc
    return None


def load_json_safe(path: Path) -> Tuple[Optional[Dict], Optional[str]]:
    """Load JSON safely."""
    try:
        if path.stat().st_size == 0:
            return None, "Empty file"
        with open(path, 'r') as f:
            return json.load(f), None
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON: {e}"
    except Exception as e:
        return None, f"Read error: {e}"


def extract_metadata_from_path(task_dir: Path) -> Dict[str, Any]:
    """Extract model_slug, app_number, task_id from directory path."""
    parts = task_dir.parts
    task_id = task_dir.name
    app_name = task_dir.parent.name
    model_slug = task_dir.parent.parent.name

    app_number = 0
    if app_name.startswith('app'):
        try:
            app_number = int(app_name[3:])
        except ValueError:
            pass

    return {
        'model_slug': model_slug,
        'app_number': app_number,
        'task_id': task_id,
    }


def count_static_tools(data: Dict) -> Tuple[int, int]:
    """Count Python and JS tools in static analysis results."""
    results = data
    if 'results' in data:
        results = data['results']
    
    # Handle flat format where results directly has python/javascript
    if 'python' in results or 'javascript' in results:
        result_data = results
    elif 'analysis' in results:
        result_data = results['analysis'].get('results', {})
    else:
        result_data = results.get('results', {})

    py_count = 0
    js_count = 0
    for tool_name in result_data.get('python', {}):
        if not tool_name.startswith('_'):
            py_count += 1
    for tool_name in result_data.get('javascript', {}):
        if not tool_name.startswith('_'):
            js_count += 1
    return py_count, js_count


def get_service_status(svc_name: str, data: Dict) -> str:
    """Extract the status of a service from its JSON data."""
    # Direct status
    results = data
    if 'results' in data:
        results = data['results']

    status = results.get('status', 'unknown')
    if status in ('success', 'error', 'targets_unreachable', 'partial', 'completed'):
        return status

    # Check analysis level
    analysis = results.get('analysis', data.get('analysis', {}))
    if isinstance(analysis, dict):
        status = analysis.get('status', status)

    return status


def count_total_findings(services: Dict[str, Dict]) -> int:
    """Count total findings across all service results."""
    total = 0

    # Static findings
    static_data = services.get('static', {}).get('data')
    if static_data:
        result_data = _get_static_result_data(static_data)
        for lang, tools in result_data.items():
            if not isinstance(tools, dict):
                continue
            for tool_name, tool_data in tools.items():
                if tool_name.startswith('_') or not isinstance(tool_data, dict):
                    continue
                total += tool_data.get('issue_count', tool_data.get('total_issues', 0))

    return total


def _get_static_result_data(data: Dict) -> Dict:
    """Extract the language->tools dict from static results (handles all formats)."""
    results = data
    if 'results' in data:
        results = data['results']
    if 'python' in results or 'javascript' in results:
        return results
    if 'analysis' in results:
        return results['analysis'].get('results', {})
    return results.get('results', {})


def build_severity_breakdown(services: Dict[str, Dict]) -> Dict[str, int]:
    """Build severity breakdown across all service results."""
    breakdown = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}

    static_data = services.get('static', {}).get('data')
    if static_data:
        result_data = _get_static_result_data(static_data)
        for lang, tools in result_data.items():
            if not isinstance(tools, dict):
                continue
            for tool_name, tool_data in tools.items():
                if tool_name.startswith('_') or not isinstance(tool_data, dict):
                    continue
                issues = tool_data.get('issues', [])
                if isinstance(issues, list):
                    for issue in issues:
                        if isinstance(issue, dict):
                            sev = issue.get('severity', 'low').lower()
                            if sev in breakdown:
                                breakdown[sev] += 1
                            else:
                                breakdown['info'] += 1

    return breakdown


def standardize_task(task_dir: Path, dry_run: bool = False) -> Dict[str, Any]:
    """Standardize a single task directory."""
    report = {
        'task_dir': str(task_dir),
        'actions': [],
        'services_found': {},
        'consolidated_created': False,
    }

    svc_dir = task_dir / 'services'
    if not svc_dir.exists():
        report['actions'].append('SKIP: no services directory')
        return report

    metadata = extract_metadata_from_path(task_dir)

    # Step 1: Group files by canonical service name
    files_by_service: Dict[str, List[Dict]] = defaultdict(list)
    for f in sorted(svc_dir.glob('*.json')):
        svc = classify_service_file(f.name)
        if svc is None:
            report['actions'].append(f'SKIP: unclassified file {f.name}')
            continue
        data, err = load_json_safe(f)
        if err:
            report['actions'].append(f'SKIP: {f.name} - {err}')
            continue
        files_by_service[svc].append({
            'path': f,
            'name': f.name,
            'size': f.stat().st_size,
            'data': data,
        })

    # Step 2: For each service, pick the best file and rename to canonical
    service_results = {}
    for svc, files in files_by_service.items():
        # Pick largest file (most complete)
        files.sort(key=lambda x: x['size'], reverse=True)
        best = files[0]

        canonical_name = f'{svc}.json'
        canonical_path = svc_dir / canonical_name

        service_results[svc] = {
            'file': canonical_name,
            'size': best['size'],
            'data': best['data'],
            'status': get_service_status(svc, best['data']),
        }

        # Rename if needed
        if best['path'].name != canonical_name:
            if dry_run:
                report['actions'].append(f'RENAME: {best["name"]} -> {canonical_name}')
            else:
                # Write canonical file
                with open(canonical_path, 'w', encoding='utf-8') as f:
                    json.dump(best['data'], f, indent=2, default=str)
                report['actions'].append(f'RENAMED: {best["name"]} -> {canonical_name}')

        # Remove duplicates
        for dup in files[1:]:
            if dup['path'].name == canonical_name:
                continue
            if dry_run:
                report['actions'].append(f'REMOVE_DUP: {dup["name"]} ({dup["size"]} bytes)')
            else:
                dup['path'].unlink()
                report['actions'].append(f'REMOVED_DUP: {dup["name"]}')

        # Remove old-format prefixed files that are now duplicates
        for f in svc_dir.glob(f'*_{svc}.json'):
            if f.name != canonical_name and f.name not in [best['name']]:
                if dry_run:
                    report['actions'].append(f'REMOVE_PREFIX: {f.name}')
                else:
                    f.unlink()
                    report['actions'].append(f'REMOVED_PREFIX: {f.name}')

    # Remove .old files
    for f in svc_dir.glob('*.old*'):
        if dry_run:
            report['actions'].append(f'REMOVE_OLD: {f.name}')
        else:
            f.unlink()
            report['actions'].append(f'REMOVED_OLD: {f.name}')

    report['services_found'] = {
        svc: {'file': info['file'], 'status': info['status'], 'size': info['size']}
        for svc, info in service_results.items()
    }

    # Step 3: Generate consolidated.json
    total_findings = count_total_findings(service_results)
    severity = build_severity_breakdown(service_results)
    tools_executed = 0
    # Count tools from static
    static_data = service_results.get('static', {}).get('data')
    if static_data:
        py, js = count_static_tools(static_data)
        tools_executed += py + js

    consolidated = {
        'metadata': {
            'model_slug': metadata['model_slug'],
            'app_number': metadata['app_number'],
            'task_id': metadata['task_id'],
            'created_at': datetime.now(timezone.utc).isoformat(),
            'version': '2.0',
            'standardized': True,
        },
        'summary': {
            'status': _determine_overall_status(service_results),
            'total_findings': total_findings,
            'services_executed': len(service_results),
            'tools_executed': tools_executed,
            'severity_breakdown': severity,
        },
        'services': {},
    }

    for svc, info in service_results.items():
        consolidated['services'][svc] = {
            'status': info['status'],
            'file': f'services/{info["file"]}',
        }

    consolidated_path = task_dir / 'consolidated.json'
    if dry_run:
        report['actions'].append(f'CREATE: consolidated.json')
    else:
        with open(consolidated_path, 'w', encoding='utf-8') as f:
            json.dump(consolidated, f, indent=2, default=str)
        report['actions'].append(f'CREATED: consolidated.json')

    report['consolidated_created'] = True

    # Step 4: Update manifest
    manifest = {
        'task_id': metadata['task_id'],
        'model_slug': metadata['model_slug'],
        'app_number': metadata['app_number'],
        'created_at': datetime.now(timezone.utc).isoformat(),
        'services': list(service_results.keys()),
        'files': sorted(f.name for f in task_dir.glob('*') if f.is_file()),
    }
    manifest_path = task_dir / 'manifest.json'
    if not dry_run:
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)

    return report


def _determine_overall_status(services: Dict[str, Dict]) -> str:
    """Determine overall status from service statuses."""
    statuses = [info.get('status', 'unknown') for info in services.values()]
    if all(s == 'success' for s in statuses):
        return 'success'
    if all(s in ('error', 'targets_unreachable') for s in statuses):
        return 'failed'
    return 'partial'


def run_standardization(results_dir: Path, dry_run: bool = False) -> Dict[str, Any]:
    """Run standardization across all results."""
    summary = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'dry_run': dry_run,
        'total_tasks': 0,
        'tasks_standardized': 0,
        'consolidated_created': 0,
        'files_renamed': 0,
        'files_removed': 0,
        'errors': [],
        'per_model': {},
    }

    for model_dir in sorted(results_dir.iterdir()):
        if not model_dir.is_dir() or model_dir.name.endswith('.json'):
            continue

        model_slug = model_dir.name
        model_summary = {'apps': {}, 'total_tasks': 0, 'standardized': 0}

        for app_dir in sorted(model_dir.iterdir()):
            if not app_dir.is_dir() or not app_dir.name.startswith('app'):
                continue

            app_name = app_dir.name
            app_tasks = []

            for task_dir in sorted(app_dir.iterdir()):
                if not task_dir.is_dir() or not task_dir.name.startswith('task'):
                    continue

                summary['total_tasks'] += 1
                model_summary['total_tasks'] += 1

                try:
                    result = standardize_task(task_dir, dry_run=dry_run)
                    app_tasks.append(result)

                    if result['consolidated_created']:
                        summary['consolidated_created'] += 1

                    for action in result['actions']:
                        if 'RENAME' in action:
                            summary['files_renamed'] += 1
                        if 'REMOVE' in action:
                            summary['files_removed'] += 1

                    summary['tasks_standardized'] += 1
                    model_summary['standardized'] += 1

                except Exception as e:
                    summary['errors'].append(f'{model_slug}/{app_name}/{task_dir.name}: {e}')

            model_summary['apps'][app_name] = {
                'task_count': len(app_tasks),
                'services': {
                    t.get('task_dir', '').split('/')[-1]: list(t.get('services_found', {}).keys())
                    for t in app_tasks
                }
            }

        summary['per_model'][model_slug] = model_summary

    return summary


def print_summary(summary: Dict[str, Any]) -> None:
    """Print human-readable summary."""
    print("=" * 70)
    print(f"STANDARDIZATION {'(DRY RUN)' if summary['dry_run'] else 'COMPLETED'}")
    print("=" * 70)
    print(f"Timestamp: {summary['timestamp']}")
    print()
    print(f"  Tasks processed:        {summary['total_tasks']}")
    print(f"  Tasks standardized:     {summary['tasks_standardized']}")
    print(f"  Consolidated created:   {summary['consolidated_created']}")
    print(f"  Files renamed:          {summary['files_renamed']}")
    print(f"  Files removed:          {summary['files_removed']}")
    print()

    if summary['errors']:
        print(f"  ERRORS ({len(summary['errors'])}):")
        for err in summary['errors']:
            print(f"    - {err}")
        print()

    print("--- Per-Model ---")
    for model, data in summary['per_model'].items():
        print(f"  {model}: {data['total_tasks']} tasks, {data['standardized']} standardized")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Standardize and consolidate analysis results')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
    parser.add_argument('--results-dir', type=str, default=str(RESULTS_DIR))
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    args = parser.parse_args()

    results_path = Path(args.results_dir)
    summary = run_standardization(results_path, dry_run=args.dry_run)

    if args.json:
        print(json.dumps(summary, indent=2, default=str))
    else:
        print_summary(summary)
