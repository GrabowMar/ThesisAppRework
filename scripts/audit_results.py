#!/usr/bin/env python3
"""
Results Audit Script
====================

Scans all analysis results directories and validates:
- JSON file integrity
- Static analysis tool counts (10 Python + 2 JS expected)
- AI analysis score ranges and confidence levels
- Service file completeness
- File naming consistency
- Identifies best task per app (for deduplication)

Outputs a detailed audit report.
"""
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

RESULTS_DIR = Path(__file__).parent.parent / 'results'

EXPECTED_PYTHON_TOOLS = {
    'bandit', 'pylint', 'semgrep', 'mypy', 'safety',
    'pip-audit', 'vulture', 'ruff', 'radon', 'detect-secrets'
}
EXPECTED_JS_TOOLS = {'eslint', 'npm-audit'}
VALID_CONFIDENCE = {'HIGH', 'MEDIUM', 'LOW'}

# File naming patterns
SERVICE_NAME_MAP = {
    'static-analyzer': 'static',
    'dynamic-analyzer': 'dynamic',
    'performance-tester': 'performance',
    'ai-analyzer': 'ai',
}


def load_json_safe(path: Path) -> Tuple[Optional[Dict], Optional[str]]:
    """Load JSON file safely, returning (data, error)."""
    try:
        if path.stat().st_size == 0:
            return None, "Empty file"
        with open(path, 'r') as f:
            return json.load(f), None
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON: {e}"
    except Exception as e:
        return None, f"Read error: {e}"


def classify_service_file(filename: str) -> Optional[str]:
    """Classify a service file to its canonical service name."""
    name = filename.lower()
    if name.endswith('.old') or '.old_' in name:
        return None
    for pattern, canonical in SERVICE_NAME_MAP.items():
        if pattern in name:
            return canonical
    for svc in ('static', 'dynamic', 'performance', 'ai'):
        if f'_{svc}.json' in name or name == f'{svc}.json':
            return svc
    return None


def validate_static_results(data: Dict) -> Dict[str, Any]:
    """Validate static analysis results."""
    issues = []
    tool_info = {'python_tools': [], 'js_tools': [], 'other_tools': []}

    # Navigate to results - handle different structures
    # Format 1: {results: {analysis: {results: {python: ...}}}}
    # Format 2: {results: {python: ...}} (flat format from static-analyzer)
    # Format 3: {metadata: ..., results: {type: ..., analysis: {results: {python: ...}}}}
    results = data
    if 'results' in data:
        results = data['results']
    
    # Check if results directly contains language keys (flat format)
    if 'python' in results or 'javascript' in results:
        result_data = results
    elif 'analysis' in results:
        analysis = results['analysis']
        result_data = analysis.get('results', {})
    elif 'analysis' in data:
        analysis = data['analysis']
        result_data = analysis.get('results', {})
    else:
        result_data = results.get('results', {})

    # Check Python tools
    python_results = result_data.get('python', {})
    for tool_name, tool_data in python_results.items():
        if tool_name.startswith('_'):
            continue  # Skip metadata entries
        if isinstance(tool_data, dict):
            executed = tool_data.get('executed', False)
            status = tool_data.get('status', 'unknown')
            tool_info['python_tools'].append({
                'name': tool_name,
                'executed': executed,
                'status': status,
                'issue_count': tool_data.get('issue_count', tool_data.get('total_issues', 0))
            })

    # Check JS tools
    js_results = result_data.get('javascript', {})
    for tool_name, tool_data in js_results.items():
        if tool_name.startswith('_'):
            continue  # Skip metadata entries
        if isinstance(tool_data, dict):
            executed = tool_data.get('executed', False)
            status = tool_data.get('status', 'unknown')
            tool_info['js_tools'].append({
                'name': tool_name,
                'executed': executed,
                'status': status,
                'issue_count': tool_data.get('issue_count', tool_data.get('total_issues', 0))
            })

    # Count tools
    py_tool_names = {t['name'] for t in tool_info['python_tools']}
    js_tool_names = {t['name'] for t in tool_info['js_tools']}

    missing_py = EXPECTED_PYTHON_TOOLS - py_tool_names
    missing_js = EXPECTED_JS_TOOLS - js_tool_names

    if missing_py:
        issues.append(f"Missing Python tools: {missing_py}")
    if missing_js:
        issues.append(f"Missing JS tools: {missing_js}")

    # Check for tools that didn't execute
    for t in tool_info['python_tools'] + tool_info['js_tools']:
        if not t['executed']:
            issues.append(f"Tool {t['name']} not executed")

    total_findings = sum(
        t.get('issue_count', 0) for t in tool_info['python_tools'] + tool_info['js_tools']
    )

    return {
        'valid': len(issues) == 0,
        'python_tool_count': len(py_tool_names),
        'js_tool_count': len(js_tool_names),
        'total_findings': total_findings,
        'missing_python': list(missing_py),
        'missing_js': list(missing_js),
        'issues': issues,
    }


def validate_ai_results(data: Dict) -> Dict[str, Any]:
    """Validate AI analysis results."""
    issues = []

    results = data
    if 'results' in data:
        results = data['results']

    analysis = results.get('analysis', results)
    tools = analysis.get('tools', {})

    if not tools:
        return {'valid': False, 'issues': ['No tools found in AI results'], 'tools_found': []}

    tools_found = list(tools.keys())

    for tool_name, tool_data in tools.items():
        if not isinstance(tool_data, dict):
            issues.append(f"Tool {tool_name}: invalid data type")
            continue

        status = tool_data.get('status', 'unknown')
        if status not in ('success', 'error', 'skipped'):
            issues.append(f"Tool {tool_name}: unexpected status '{status}'")

        # Check requirements results
        tool_results = tool_data.get('results', {})
        for req_category in ('backend_requirements', 'frontend_requirements', 'admin_requirements'):
            reqs = tool_results.get(req_category, [])
            for req in reqs:
                if not isinstance(req, dict):
                    continue
                confidence = req.get('confidence', '')
                if confidence and confidence not in VALID_CONFIDENCE:
                    issues.append(f"Tool {tool_name}: invalid confidence '{confidence}' in {req_category}")
                met = req.get('met')
                if met is not None and not isinstance(met, bool):
                    issues.append(f"Tool {tool_name}: 'met' should be bool, got {type(met).__name__}")

    return {
        'valid': len(issues) == 0,
        'tools_found': tools_found,
        'issues': issues,
    }


def validate_dynamic_results(data: Dict) -> Dict[str, Any]:
    """Validate dynamic analysis results."""
    issues = []
    results = data
    if 'results' in data:
        results = data['results']

    status = results.get('status', 'unknown')
    # targets_unreachable is expected when containers aren't running
    is_unreachable = status in ('targets_unreachable', 'error')

    return {
        'valid': True,  # Dynamic failures are expected
        'status': status,
        'targets_unreachable': is_unreachable,
        'issues': issues,
    }


def validate_performance_results(data: Dict) -> Dict[str, Any]:
    """Validate performance test results."""
    results = data
    if 'results' in data:
        results = data['results']

    status = results.get('status', 'unknown')
    is_unreachable = status in ('targets_unreachable', 'error')

    return {
        'valid': True,  # Performance failures are expected
        'status': status,
        'targets_unreachable': is_unreachable,
        'issues': [],
    }


def find_best_task(app_dir: Path) -> Optional[Path]:
    """Find the best (most complete) task directory for an app."""
    task_dirs = sorted(app_dir.glob('task_*'), key=lambda p: p.stat().st_mtime, reverse=True)
    
    best = None
    best_score = -1

    for task_dir in task_dirs:
        svc_dir = task_dir / 'services'
        if not svc_dir.exists():
            continue

        score = 0
        services_found = set()
        for f in svc_dir.glob('*.json'):
            svc = classify_service_file(f.name)
            if svc and svc not in services_found:
                services_found.add(svc)
                # Check file is valid JSON with real content
                data, err = load_json_safe(f)
                if data and not err:
                    score += 10
                    # Bonus for static with full tools
                    if svc == 'static':
                        val = validate_static_results(data)
                        score += val['python_tool_count'] + val['js_tool_count']

        if score > best_score:
            best_score = score
            best = task_dir

    return best


def audit_results(results_dir: Path) -> Dict[str, Any]:
    """Run full audit on results directory."""
    report = {
        'timestamp': datetime.utcnow().isoformat(),
        'results_dir': str(results_dir),
        'models': {},
        'summary': {
            'total_models': 0,
            'total_apps': 0,
            'total_tasks': 0,
            'tasks_with_consolidated': 0,
            'tasks_with_all_services': 0,
            'naming_issues': 0,
            'corrupted_files': 0,
            'static_complete': 0,
            'static_incomplete': 0,
            'ai_valid': 0,
            'ai_invalid': 0,
            'dynamic_unreachable': 0,
            'performance_unreachable': 0,
            'apps_with_multiple_tasks': 0,
            'best_tasks': [],  # (model, app, task_id) for the best task per app
            'issues': [],
        }
    }

    if not results_dir.exists():
        report['summary']['issues'].append(f"Results directory not found: {results_dir}")
        return report

    for model_dir in sorted(results_dir.iterdir()):
        if not model_dir.is_dir() or model_dir.name.endswith('.json'):
            continue

        model_slug = model_dir.name
        report['summary']['total_models'] += 1
        model_report = {'apps': {}}

        for app_dir in sorted(model_dir.iterdir()):
            if not app_dir.is_dir() or not app_dir.name.startswith('app'):
                continue

            app_name = app_dir.name
            report['summary']['total_apps'] += 1

            task_dirs = list(app_dir.glob('task_*'))
            if len(task_dirs) > 1:
                report['summary']['apps_with_multiple_tasks'] += 1

            # Find best task
            best_task = find_best_task(app_dir)

            app_report = {'tasks': {}, 'best_task': None, 'task_count': len(task_dirs)}

            for task_dir in sorted(task_dirs):
                if not task_dir.is_dir():
                    continue

                task_id = task_dir.name
                report['summary']['total_tasks'] += 1
                is_best = best_task and task_dir == best_task

                task_report = {
                    'is_best': is_best,
                    'has_consolidated': (task_dir / 'consolidated.json').exists(),
                    'has_manifest': (task_dir / 'manifest.json').exists(),
                    'has_sarif': (task_dir / 'sarif').exists(),
                    'services': {},
                    'naming_patterns': [],
                    'file_issues': [],
                }

                if task_report['has_consolidated']:
                    report['summary']['tasks_with_consolidated'] += 1

                # Scan service files
                svc_dir = task_dir / 'services'
                if svc_dir.exists():
                    services_found = {}
                    for f in sorted(svc_dir.glob('*.json')):
                        svc = classify_service_file(f.name)
                        if svc is None:
                            task_report['naming_patterns'].append(f"unclassified: {f.name}")
                            continue

                        # Track naming pattern
                        if f.name == f'{svc}.json':
                            pattern = 'short'
                        elif f.name.startswith(model_slug):
                            pattern = 'prefixed'
                        elif '-analyzer' in f.name or '-tester' in f.name:
                            pattern = 'service-name'
                        else:
                            pattern = 'other'

                        task_report['naming_patterns'].append(f"{svc}:{pattern}")

                        # Load and validate
                        data, err = load_json_safe(f)
                        if err:
                            task_report['file_issues'].append(f"{f.name}: {err}")
                            report['summary']['corrupted_files'] += 1
                            continue

                        # Keep the best version (largest file = most data)
                        if svc in services_found:
                            old_size = services_found[svc]['size']
                            new_size = f.stat().st_size
                            if new_size > old_size:
                                services_found[svc] = {'file': f.name, 'size': new_size, 'data': data}
                                report['summary']['naming_issues'] += 1
                        else:
                            services_found[svc] = {'file': f.name, 'size': f.stat().st_size, 'data': data}

                    # Validate each service
                    for svc, info in services_found.items():
                        svc_report = {'file': info['file'], 'size': info['size']}

                        if svc == 'static':
                            val = validate_static_results(info['data'])
                            svc_report['validation'] = val
                            if val['valid'] and val['python_tool_count'] >= 10 and val['js_tool_count'] >= 2:
                                report['summary']['static_complete'] += 1
                            else:
                                report['summary']['static_incomplete'] += 1
                        elif svc == 'ai':
                            val = validate_ai_results(info['data'])
                            svc_report['validation'] = val
                            if val['valid']:
                                report['summary']['ai_valid'] += 1
                            else:
                                report['summary']['ai_invalid'] += 1
                        elif svc == 'dynamic':
                            val = validate_dynamic_results(info['data'])
                            svc_report['validation'] = val
                            if val.get('targets_unreachable'):
                                report['summary']['dynamic_unreachable'] += 1
                        elif svc == 'performance':
                            val = validate_performance_results(info['data'])
                            svc_report['validation'] = val
                            if val.get('targets_unreachable'):
                                report['summary']['performance_unreachable'] += 1

                        task_report['services'][svc] = svc_report

                    if len(services_found) == 4:
                        report['summary']['tasks_with_all_services'] += 1

                app_report['tasks'][task_id] = task_report
                if is_best:
                    app_report['best_task'] = task_id
                    report['summary']['best_tasks'].append({
                        'model': model_slug,
                        'app': app_name,
                        'task': task_id,
                        'services': list(task_report['services'].keys()),
                    })

            model_report['apps'][app_name] = app_report

        report['models'][model_slug] = model_report

    return report


def print_summary(report: Dict[str, Any]) -> None:
    """Print human-readable audit summary."""
    s = report['summary']
    print("=" * 70)
    print("ANALYSIS RESULTS AUDIT REPORT")
    print("=" * 70)
    print(f"Timestamp: {report['timestamp']}")
    print(f"Results dir: {report['results_dir']}")
    print()

    print("--- Overview ---")
    print(f"  Models:       {s['total_models']}")
    print(f"  Apps:         {s['total_apps']}")
    print(f"  Tasks:        {s['total_tasks']}")
    print(f"  Multi-task apps: {s['apps_with_multiple_tasks']}")
    print()

    print("--- File Status ---")
    print(f"  With consolidated.json: {s['tasks_with_consolidated']}/{s['total_tasks']}")
    print(f"  With all 4 services:    {s['tasks_with_all_services']}/{s['total_tasks']}")
    print(f"  Naming issues:          {s['naming_issues']}")
    print(f"  Corrupted files:        {s['corrupted_files']}")
    print()

    print("--- Static Analysis ---")
    print(f"  Complete (10Py+2JS): {s['static_complete']}")
    print(f"  Incomplete:          {s['static_incomplete']}")
    print()

    print("--- AI Analysis ---")
    print(f"  Valid:   {s['ai_valid']}")
    print(f"  Invalid: {s['ai_invalid']}")
    print()

    print("--- Dynamic/Performance ---")
    print(f"  Dynamic unreachable:     {s['dynamic_unreachable']} (expected)")
    print(f"  Performance unreachable: {s['performance_unreachable']} (expected)")
    print()

    # Print per-model summary
    print("--- Per-Model Summary ---")
    for model_slug, model_data in report['models'].items():
        app_count = len(model_data['apps'])
        best_count = sum(1 for a in model_data['apps'].values() if a['best_task'])
        total_tasks = sum(a['task_count'] for a in model_data['apps'].values())
        print(f"  {model_slug}: {app_count} apps, {total_tasks} tasks, {best_count} best-picks")

    print()

    # Print issues per model
    print("--- Issues by Model ---")
    for model_slug, model_data in report['models'].items():
        model_issues = []
        for app_name, app_data in model_data['apps'].items():
            for task_id, task_data in app_data['tasks'].items():
                if not task_data['is_best']:
                    continue
                # Check missing services
                missing_svcs = {'static', 'dynamic', 'performance', 'ai'} - set(task_data['services'].keys())
                if missing_svcs:
                    model_issues.append(f"  {app_name}/{task_id}: missing {missing_svcs}")
                # Check static validation
                static = task_data['services'].get('static', {})
                val = static.get('validation', {})
                if val and not val.get('valid', True):
                    model_issues.append(f"  {app_name}/{task_id}: static issues: {val.get('issues', [])}")
                # Check AI validation
                ai = task_data['services'].get('ai', {})
                val = ai.get('validation', {})
                if val and not val.get('valid', True):
                    model_issues.append(f"  {app_name}/{task_id}: AI issues: {val.get('issues', [])}")
                # Check file issues
                for issue in task_data.get('file_issues', []):
                    model_issues.append(f"  {app_name}/{task_id}: {issue}")

        if model_issues:
            print(f"\n  {model_slug}:")
            for issue in model_issues:
                print(f"    {issue}")
        else:
            print(f"  {model_slug}: ✓ No issues in best tasks")

    # Print best task summary
    print()
    print("--- Best Tasks Summary ---")
    print(f"  Total best tasks identified: {len(s['best_tasks'])}")
    for bt in s['best_tasks']:
        svcs = ', '.join(bt['services'])
        print(f"  {bt['model']}/{bt['app']}: {bt['task']} [{svcs}]")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Audit analysis results')
    parser.add_argument('--results-dir', type=str, default=str(RESULTS_DIR),
                        help='Path to results directory')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--json-output', type=str, help='Save JSON report to file')
    args = parser.parse_args()

    results_path = Path(args.results_dir)
    report = audit_results(results_path)

    if args.json or args.json_output:
        # Remove data references for JSON output (too large)
        for model in report.get('models', {}).values():
            for app in model.get('apps', {}).values():
                for task in app.get('tasks', {}).values():
                    for svc in task.get('services', {}).values():
                        svc.pop('data', None)

        json_str = json.dumps(report, indent=2, default=str)
        if args.json_output:
            with open(args.json_output, 'w') as f:
                f.write(json_str)
            print(f"JSON report saved to: {args.json_output}")
        else:
            print(json_str)
    else:
        print_summary(report)
