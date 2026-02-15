#!/usr/bin/env python3
"""
Thesis Data Extraction Script — Tool-Centric Chapter 7
=======================================================

Extracts all analysis data from raw result files and generates
thesis-ready JSON tables. Run this after each pipeline completion
to update the data for the results chapter.

Usage:
    cd ThesisAppRework
    python3 scripts/extract_thesis_data.py [--output FILE]

Output: JSON file with all thesis tables, printed summary to stdout.
"""

import json
import statistics
import argparse
import os
from collections import defaultdict
from pathlib import Path


MODEL_SHORT_NAMES = {
    'anthropic_claude-4.5-sonnet-20250929': 'Claude 4.5 Sonnet',
    'deepseek_deepseek-r1-0528': 'DeepSeek R1',
    'google_gemini-3-flash-preview-20251217': 'Gemini 3 Flash',
    'google_gemini-3-pro-preview-20251117': 'Gemini 3 Pro',
    'meta-llama_llama-3.1-405b-instruct': 'Llama 3.1 405B',
    'mistralai_mistral-small-3.1-24b-instruct-2503': 'Mistral Small 3.1',
    'openai_gpt-4o-mini': 'GPT-4o Mini',
    'openai_gpt-5.2-codex-20260114': 'GPT-5.2 Codex',
    'qwen_qwen3-coder-plus': 'Qwen3 Coder+',
    'z-ai_glm-4.7-20251222': 'GLM-4.7',
}

# File extensions for LOC counting
EXT_MAP = {
    '.py': 'python', '.js': 'javascript', '.jsx': 'jsx', '.tsx': 'jsx',
    '.css': 'css', '.html': 'html', '.htm': 'html',
}

SKIP_EXTS = {
    '.json', '.lock', '.map', '.svg', '.png', '.jpg', '.gif',
    '.ico', '.woff', '.woff2', '.ttf', '.eot', '.md', '.txt',
}

SKIP_DIRS = {'node_modules', '__pycache__', 'venv', '.git', 'dist', 'build'}


def count_loc(gen_dir: Path) -> dict:
    """Count lines of code per model from generated apps."""
    model_loc = {}
    for model_dir in sorted(gen_dir.iterdir()):
        if not model_dir.is_dir():
            continue
        model_slug = model_dir.name
        model_loc[model_slug] = {'python': 0, 'javascript': 0, 'jsx': 0,
                                  'css': 0, 'html': 0, 'other': 0,
                                  'total': 0, 'apps': 0}
        for app_dir in sorted(model_dir.iterdir()):
            if not app_dir.is_dir():
                continue
            model_loc[model_slug]['apps'] += 1
            for root, dirs, files in os.walk(app_dir):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for f in files:
                    ext = Path(f).suffix.lower()
                    if ext in SKIP_EXTS:
                        continue
                    lang = EXT_MAP.get(ext, 'other')
                    try:
                        lines = (Path(root) / f).read_text(errors='ignore').count('\n')
                        model_loc[model_slug][lang] += lines
                        model_loc[model_slug]['total'] += lines
                    except Exception:
                        pass
    return model_loc


def extract_all_data(results_dir: Path, gen_dir: Path) -> dict:
    """Extract all thesis data from raw result files."""
    # Data structures
    tool_model = defaultdict(lambda: defaultdict(
        lambda: {'runs': 0, 'findings': 0,
                 'severity': {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}}
    ))
    model_app_findings = defaultdict(lambda: defaultdict(int))
    model_app_severity = defaultdict(lambda: defaultdict(
        lambda: {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
    ))
    perf_model = defaultdict(lambda: {'backend_rps': [], 'backend_rt': [],
                                       'frontend_rps': [], 'frontend_rt': [],
                                       'tests': 0})
    # Per-tool performance metrics: perf_tool_model[tool][model] = {rps:[], rt:[], ...}
    perf_tool_model = defaultdict(lambda: defaultdict(
        lambda: {'rps': [], 'avg_rt': [], 'requests': [], 'errors': [],
                 'p95_rt': [], 'runs': 0}
    ))
    ai_model = defaultdict(lambda: {'overall': [], 'backend': [], 'frontend': [],
                                     'admin': [], 'apps': 0})
    # Per-tool AI metrics: ai_tool_model[tool][model] = {scores:[], runs:0, ...}
    ai_tool_model = defaultdict(lambda: defaultdict(
        lambda: {'runs': 0, 'scores': [], 'grades': [],
                 'compliance_pcts': [], 'metrics_passed': [], 'metrics_total': []}
    ))
    zap_model = defaultdict(lambda: {'alerts': 0, 'scans': 0, 'attempted_scans': 0, 'scans_with_alerts': 0,
                                       'by_risk': defaultdict(int),
                                       'cwes': defaultdict(int),
                                       'alert_types': defaultdict(int)})
    dyn_diag_model = defaultdict(lambda: {
        'apps_with_any_output': 0,
        'port_scan_attempted': 0,
        'port_scan_success': 0,
        'open_ports_total': 0,
        'apps_with_open_ports': 0,
        'open_port_counts': defaultdict(int),
        'curl_attempted': 0,
        'curl_success': 0,
        'endpoints_total': 0,
        'endpoints_passed': 0,
    })
    service_completion = defaultdict(lambda: {'success': 0, 'total': 0})
    app_count = 0
    processed_app_count = 0

    for model_dir in sorted(results_dir.iterdir()):
        if not model_dir.is_dir():
            continue
        model_slug = model_dir.name
        for app_dir in sorted(model_dir.iterdir()):
            if not app_dir.is_dir():
                continue
            app_n = app_dir.name
            app_count += 1

            # Each app can contain multiple task runs and multiple JSON snapshots per task.
            # For thesis aggregation we count *one consolidated result per app* to avoid double-counting.
            task_candidates = []
            for task_dir in app_dir.iterdir():
                if not task_dir.is_dir():
                    continue
                manifest = task_dir / 'manifest.json'
                ts = ''
                main_path = None
                if manifest.exists():
                    try:
                        m = json.loads(manifest.read_text())
                        ts = m.get('timestamp') or ''
                        main_file = m.get('main_result_file')
                        if main_file:
                            p = task_dir / main_file
                            if p.exists():
                                main_path = p
                    except Exception:
                        # fall back to selecting the latest JSON snapshot below
                        pass

                # Fallback: some manifests can be stale/wrong; pick the latest JSON snapshot in the task dir.
                if main_path is None:
                    json_candidates = [
                        p for p in task_dir.iterdir()
                        if p.is_file() and p.name.endswith('.json') and p.name != 'manifest.json'
                    ]
                    if not json_candidates:
                        continue
                    json_candidates.sort(key=lambda p: p.name)
                    main_path = json_candidates[-1]

                task_candidates.append((ts, main_path))

            # Prefer the latest task (by manifest timestamp).
            if not task_candidates:
                continue
            task_candidates.sort(key=lambda x: x[0])
            _, main_result_path = task_candidates[-1]

            try:
                data = json.loads(main_result_path.read_text())
            except Exception:
                continue
            processed_app_count += 1

            services = data.get('services', {})
            _process_static(services, model_slug, app_n, tool_model,
                             model_app_findings, model_app_severity, service_completion)
            _process_dynamic(services, model_slug, app_n, tool_model, zap_model,
                             dyn_diag_model, service_completion)
            _process_performance(services, model_slug, perf_model, perf_tool_model,
                                 service_completion)
            _process_ai(services, model_slug, ai_model, ai_tool_model, service_completion)

    loc_data = count_loc(gen_dir) if gen_dir.exists() else {}
    return _build_output(tool_model, model_app_findings, model_app_severity,
                         perf_model, perf_tool_model, ai_model, ai_tool_model,
                         zap_model, dyn_diag_model, service_completion,
                         loc_data, app_count, processed_app_count)


def _process_static(services: dict, model_slug: str, app_n: str,
                     tool_model: dict, model_app_findings: dict,
                     model_app_severity: dict, service_completion: dict) -> None:
    static = services.get('static-analyzer', {})
    service_completion['static']['total'] += 1
    if static.get('status') != 'success':
        return
    service_completion['static']['success'] += 1
    analysis = static.get('payload', {}).get('analysis', {})
    results = analysis.get('results', {})
    for lang, lang_tools in results.items():
        if not isinstance(lang_tools, dict):
            continue
        for tn, td in lang_tools.items():
            if tn.startswith('_') or not isinstance(td, dict):
                continue
            if not td.get('executed', False):
                continue
            issues = td.get('issues', [])
            count = td.get('issue_count', len(issues) if isinstance(issues, list) else 0)
            tool_model[tn][model_slug]['runs'] += 1
            tool_model[tn][model_slug]['findings'] += count
            model_app_findings[model_slug][app_n] += count
            sb = td.get('severity_breakdown', {})
            for sev, cnt in sb.items():
                if sev in tool_model[tn][model_slug]['severity']:
                    tool_model[tn][model_slug]['severity'][sev] += cnt
                    model_app_severity[model_slug][app_n][sev] += cnt


def _process_dynamic(services: dict, model_slug: str, app_n: str,
                      tool_model: dict,
                      zap_model: dict, dyn_diag_model: dict,
                      service_completion: dict) -> None:
    dyn = services.get('dynamic-analyzer', {})
    service_completion['dynamic']['total'] += 1
    if dyn.get('status') == 'success':
        service_completion['dynamic']['success'] += 1
    analysis = dyn.get('payload', {}).get('analysis', {})
    results = analysis.get('results', {})
    tool_results = analysis.get('tool_results', {})
    if not isinstance(results, dict) or not results:
        return

    any_output = False

    connectivity = results.get('connectivity')
    if (isinstance(connectivity, list) and connectivity) or (isinstance(connectivity, dict) and connectivity):
        any_output = True

    # --- ZAP (existing logic) ---
    zap = results.get('zap_security_scan')
    scans = zap if isinstance(zap, list) else ([zap] if isinstance(zap, dict) else [])
    zap_total_alerts = 0
    for scan in scans:
        if not isinstance(scan, dict):
            continue
        any_output = True
        zap_model[model_slug]['attempted_scans'] += 1
        status = str(scan.get('status') or 'success').lower()
        if status != 'success':
            continue
        zap_model[model_slug]['scans'] += 1
        total_alerts = int(scan.get('total_alerts', 0) or 0)
        if total_alerts <= 0:
            continue
        zap_model[model_slug]['scans_with_alerts'] += 1
        zap_model[model_slug]['alerts'] += total_alerts
        zap_total_alerts += total_alerts
        for risk, alerts in scan.get('alerts_by_risk', {}).items():
            if isinstance(alerts, list):
                zap_model[model_slug]['by_risk'][risk.lower()] += len(alerts)
                for a in alerts:
                    cwe = a.get('cweid', '')
                    if cwe and cwe != '-1':
                        zap_model[model_slug]['cwes'][f"CWE-{cwe}"] += 1
                    alert_name = a.get('alert', a.get('name', 'Unknown'))
                    zap_model[model_slug]['alert_types'][alert_name] += 1

    # --- Feed dynamic tools into tool_model for unified per-tool tables ---
    # ZAP: total alerts as findings, severity from by_risk
    zap_tr = tool_results.get('zap', {})
    if isinstance(zap_tr, dict) and zap_tr.get('executed', False):
        zap_issues = int(zap_tr.get('total_issues', 0) or 0)
        tool_model['zap'][model_slug]['runs'] += 1
        tool_model['zap'][model_slug]['findings'] += zap_issues
        # Map ZAP risk levels to severity
        for scan in scans:
            if not isinstance(scan, dict):
                continue
            abr = scan.get('alerts_by_risk', {})
            for risk, alerts in abr.items():
                if not isinstance(alerts, list):
                    continue
                risk_lower = risk.lower()
                sev = {'high': 'high', 'medium': 'medium', 'low': 'low',
                       'informational': 'info'}.get(risk_lower, 'info')
                tool_model['zap'][model_slug]['severity'][sev] += len(alerts)

    # Nmap
    nmap_tr = tool_results.get('nmap', {})
    if isinstance(nmap_tr, dict) and nmap_tr.get('executed', False):
        nmap_issues = int(nmap_tr.get('total_issues', 0) or 0)
        tool_model['nmap'][model_slug]['runs'] += 1
        tool_model['nmap'][model_slug]['findings'] += nmap_issues

    # Curl (HTTP probe)
    curl_tr = tool_results.get('curl', {})
    if isinstance(curl_tr, dict) and curl_tr.get('executed', False):
        curl_issues = int(curl_tr.get('total_issues', 0) or 0)
        tool_model['curl'][model_slug]['runs'] += 1
        tool_model['curl'][model_slug]['findings'] += curl_issues

    # Curl-endpoint-tester
    curl_et = results.get('curl-endpoint-tester', {})
    curl_et_tr = tool_results.get('curl-endpoint-tester', {})
    if isinstance(curl_et_tr, dict) and curl_et_tr.get('executed', False):
        cet_issues = int(curl_et_tr.get('total_issues', 0) or 0)
        tool_model['curl-endpoint-tester'][model_slug]['runs'] += 1
        tool_model['curl-endpoint-tester'][model_slug]['findings'] += cet_issues

    # Connectivity
    conn_tools = results.get('tool_runs', {}).get('connectivity', {}) if isinstance(results.get('tool_runs'), dict) else {}
    # Connectivity is tracked via the connectivity key in results
    if isinstance(connectivity, (list, dict)) and connectivity:
        tool_model['connectivity'][model_slug]['runs'] += 1
        # Connectivity doesn't produce findings

    # Port scan
    port_scan = results.get('port_scan')
    if isinstance(port_scan, dict):
        tool_model['port-scan'][model_slug]['runs'] += 1
        # Port scan doesn't produce defect findings

    # --- Additional dynamic diagnostics (existing logic) ---
    if isinstance(port_scan, dict):
        any_output = True
        dyn_diag_model[model_slug]['port_scan_attempted'] += 1
        if port_scan.get('status') == 'success':
            dyn_diag_model[model_slug]['port_scan_success'] += 1
            open_ports = port_scan.get('open_ports') or []
            try:
                total_open = int(port_scan.get('total_open'))
            except Exception:
                total_open = None
            if total_open is None:
                total_open = len(open_ports) if isinstance(open_ports, list) else 0
            dyn_diag_model[model_slug]['open_ports_total'] += total_open
            if total_open > 0:
                dyn_diag_model[model_slug]['apps_with_open_ports'] += 1
            if isinstance(open_ports, list):
                for p in set(open_ports):
                    try:
                        dyn_diag_model[model_slug]['open_port_counts'][str(int(p))] += 1
                    except Exception:
                        continue

    curl_et_data = results.get('curl-endpoint-tester')
    if isinstance(curl_et_data, dict):
        endpoint_tests = curl_et_data.get('endpoint_tests')
        total = passed = None
        if isinstance(endpoint_tests, dict):
            try:
                total = int(endpoint_tests.get('total', 0) or 0)
                passed = int(endpoint_tests.get('passed', 0) or 0)
            except Exception:
                total = passed = None
        elif isinstance(endpoint_tests, list):
            total = len(endpoint_tests)
            passed = sum(1 for t in endpoint_tests if isinstance(t, dict) and t.get('passed') is True)
        else:
            for tk, pk in (('total_endpoints', 'passed_endpoints'), ('total', 'passed')):
                if tk in curl_et_data and pk in curl_et_data:
                    try:
                        total = int(curl_et_data.get(tk, 0) or 0)
                        passed = int(curl_et_data.get(pk, 0) or 0)
                    except Exception:
                        total = passed = None
                    break

        if total is not None and total > 0 and passed is not None:
            any_output = True
            dyn_diag_model[model_slug]['curl_attempted'] += 1
            if curl_et_data.get('status') == 'success':
                dyn_diag_model[model_slug]['curl_success'] += 1
            dyn_diag_model[model_slug]['endpoints_total'] += total
            dyn_diag_model[model_slug]['endpoints_passed'] += passed

    if any_output:
        dyn_diag_model[model_slug]['apps_with_any_output'] += 1


def _process_performance(services: dict, model_slug: str,
                           perf_model: dict, perf_tool_model: dict,
                           service_completion: dict) -> None:
    perf = services.get('performance-tester', {})
    service_completion['performance']['total'] += 1
    if perf.get('status') != 'success':
        return
    service_completion['performance']['success'] += 1
    analysis = perf.get('payload', {}).get('analysis', {})
    results = analysis.get('results', {})
    for url, url_data in results.items():
        if url == 'tool_runs' or not isinstance(url_data, dict):
            continue
        is_backend = 'backend' in url

        # --- AB (existing + per-tool) ---
        ab = url_data.get('ab', {})
        if isinstance(ab, dict) and ab.get('status') == 'success':
            rps = ab.get('requests_per_second')
            rt = ab.get('avg_response_time')
            key = 'backend_rps' if is_backend else 'frontend_rps'
            rt_key = 'backend_rt' if is_backend else 'frontend_rt'
            if rps and rps > 0:
                perf_model[model_slug][key].append(rps)
                perf_model[model_slug]['tests'] += 1
            if rt and rt > 0:
                perf_model[model_slug][rt_key].append(rt)

        # --- Per-tool extraction (ab, locust, artillery, aiohttp) ---
        for tool_name in ('ab', 'locust', 'artillery', 'aiohttp'):
            td = url_data.get(tool_name, {})
            if not isinstance(td, dict) or not td:
                continue
            # Some tools have status, some don't — accept if data exists
            rps = _safe_float(td.get('requests_per_second'))
            avg_rt = _safe_float(td.get('avg_response_time'))
            reqs = _safe_float(td.get('completed_requests', td.get('requests', 0)))
            errors = _safe_float(td.get('failed_requests',
                                         td.get('failures',
                                                td.get('errors', 0))))
            p95 = _safe_float(td.get('p95_response_time'))

            ptm = perf_tool_model[tool_name][model_slug]
            ptm['runs'] += 1
            if rps is not None and rps > 0:
                ptm['rps'].append(rps)
            if avg_rt is not None and avg_rt > 0:
                ptm['avg_rt'].append(avg_rt)
            if reqs is not None:
                ptm['requests'].append(reqs)
            if errors is not None:
                ptm['errors'].append(errors)
            if p95 is not None and p95 > 0:
                ptm['p95_rt'].append(p95)


def _safe_float(val) -> float | None:
    """Convert value to float, returning None if not numeric."""
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _process_ai(services: dict, model_slug: str,
                 ai_model: dict, ai_tool_model: dict,
                 service_completion: dict) -> None:
    ai = services.get('ai-analyzer', {})
    service_completion['ai']['total'] += 1
    if ai.get('status') != 'success':
        return
    service_completion['ai']['success'] += 1
    analysis = ai.get('payload', {}).get('analysis', {})
    tools = analysis.get('tools', {})
    req = tools.get('requirements-scanner', {})
    results = req.get('results', {})
    summary = results.get('summary', req.get('requirements_summary', {}))
    if not summary or summary.get('backend_total', 0) == 0:
        return
    bt, bm = summary.get('backend_total', 0), summary.get('backend_met', 0)
    ft, fm = summary.get('frontend_total', 0), summary.get('frontend_met', 0)
    at, am = summary.get('admin_total', 0), summary.get('admin_met', 0)
    total_t = bt + ft + at
    total_m = bm + fm + am
    overall = (total_m / total_t * 100) if total_t > 0 else 0
    ai_model[model_slug]['overall'].append(overall)
    ai_model[model_slug]['backend'].append(
        summary.get('backend_compliance', (bm / bt * 100 if bt else 0)))
    ai_model[model_slug]['frontend'].append(
        summary.get('frontend_compliance', (fm / ft * 100 if ft else 0)))
    ai_model[model_slug]['admin'].append(
        summary.get('admin_compliance', (am / at * 100 if at else 0)))
    ai_model[model_slug]['apps'] += 1

    # --- Per-tool AI extraction ---
    # Requirements scanner per-tool data
    rs_atm = ai_tool_model['requirements-scanner'][model_slug]
    rs_atm['runs'] += 1
    rs_atm['compliance_pcts'].append(overall)
    rs_atm['scores'].append(overall)
    met_count = _safe_float(summary.get('requirements_met', total_m))
    total_count = _safe_float(summary.get('total_requirements', total_t))
    if met_count is not None:
        rs_atm['metrics_passed'].append(met_count)
    if total_count is not None:
        rs_atm['metrics_total'].append(total_count)

    # Code quality analyzer
    cq = tools.get('code-quality-analyzer', {})
    cq_results = cq.get('results', {})
    cq_summary = cq_results.get('summary', {})
    if cq_summary:
        cq_atm = ai_tool_model['code-quality-analyzer'][model_slug]
        cq_atm['runs'] += 1
        agg_score = _safe_float(cq_summary.get('aggregate_score'))
        if agg_score is not None:
            cq_atm['scores'].append(agg_score)
        grade = cq_summary.get('quality_grade')
        if grade:
            cq_atm['grades'].append(grade)
        cq_compliance = _safe_float(cq_summary.get('compliance_percentage'))
        if cq_compliance is not None:
            cq_atm['compliance_pcts'].append(cq_compliance)
        mp = _safe_float(cq_summary.get('metrics_passed'))
        mt = _safe_float(cq_summary.get('total_metrics'))
        if mp is not None:
            cq_atm['metrics_passed'].append(mp)
        if mt is not None:
            cq_atm['metrics_total'].append(mt)


def _safe_stats(values: list) -> dict:
    if not values:
        return {'mean': 0, 'median': 0, 'std': 0, 'min': 0, 'max': 0, 'n': 0}
    return {
        'mean': statistics.mean(values),
        'median': statistics.median(values),
        'std': statistics.stdev(values) if len(values) > 1 else 0,
        'min': min(values),
        'max': max(values),
        'n': len(values),
    }


def _build_output(tool_model, model_app_findings, model_app_severity,
                    perf_model, perf_tool_model, ai_model, ai_tool_model,
                    zap_model, dyn_diag_model, service_completion,
                    loc_data, app_count, processed_app_count) -> dict:
    output = {}

    # Overview
    _dynamic_tool_set = {'zap', 'nmap', 'curl', 'curl-endpoint-tester',
                         'connectivity', 'port-scan'}
    total_static = sum(
        sum(d['findings'] for d in tm.values())
        for tn, tm in tool_model.items() if tn not in _dynamic_tool_set
    )
    total_zap = sum(z['alerts'] for z in zap_model.values())
    output['overview'] = {
        'total_apps': app_count,
        'apps_with_results': processed_app_count,
        'total_models': len(MODEL_SHORT_NAMES),
        'total_static_findings': total_static,
        'total_zap_alerts': total_zap,
        'service_completion': {k: dict(v) for k, v in service_completion.items()},
    }

    # Static tools (exclude dynamic tool entries that are in tool_model)
    tool_tables = {}
    for tn in sorted(tool_model.keys()):
        if tn in _dynamic_tool_set:
            continue  # These go into dynamic_tools section
        tm = tool_model[tn]
        total_f = sum(d['findings'] for d in tm.values())
        total_r = sum(d['runs'] for d in tm.values())
        total_sev = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
        per_model = {}
        for ms in MODEL_SHORT_NAMES:
            d = tm.get(ms, {'runs': 0, 'findings': 0,
                            'severity': {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}})
            per_model[ms] = {
                'runs': d['runs'],
                'findings': d['findings'],
                'avg_per_run': d['findings'] / d['runs'] if d['runs'] > 0 else 0,
                'severity': d['severity'],
            }
            for sev in total_sev:
                total_sev[sev] += d['severity'].get(sev, 0)
        tool_tables[tn] = {
            'total_findings': total_f,
            'total_runs': total_r,
            'avg_per_run': total_f / total_r if total_r > 0 else 0,
            'severity': total_sev,
            'per_model': per_model,
        }
    output['static_tools'] = tool_tables

    # ZAP
    all_cwes = defaultdict(int)
    all_alert_types = defaultdict(int)
    zap_output = {}
    for ms in MODEL_SHORT_NAMES:
        z = zap_model.get(ms, {'alerts': 0, 'scans': 0, 'attempted_scans': 0, 'scans_with_alerts': 0, 'by_risk': {}, 'cwes': {}, 'alert_types': {}})
        zap_output[ms] = {
            'scans': z['scans'],
            'attempted_scans': z.get('attempted_scans', 0),
            'alerts': z['alerts'],
            'scans_with_alerts': z.get('scans_with_alerts', 0),
            'high': z['by_risk'].get('high', 0),
            'medium': z['by_risk'].get('medium', 0),
            'low': z['by_risk'].get('low', 0),
            'informational': z['by_risk'].get('informational', 0),
        }
        for cwe, cnt in z.get('cwes', {}).items():
            all_cwes[cwe] += cnt
        for at, cnt in z.get('alert_types', {}).items():
            all_alert_types[at] += cnt
    output['dynamic_zap'] = {
        'per_model': zap_output,
        'top_cwes': dict(sorted(all_cwes.items(), key=lambda x: -x[1])[:15]),
        'top_alert_types': dict(sorted(all_alert_types.items(), key=lambda x: -x[1])[:15]),
        'total_alerts': total_zap,
        'total_scans': sum(z['scans'] for z in zap_model.values()),
        'total_attempted_scans': sum(z.get('attempted_scans', 0) for z in zap_model.values()),
        'total_scans_with_alerts': sum(z.get('scans_with_alerts', 0) for z in zap_model.values()),
    }

    # Dynamic diagnostics (beyond ZAP)
    all_open_ports = defaultdict(int)
    diag_per_model = {}
    for ms in MODEL_SHORT_NAMES:
        d = dyn_diag_model.get(ms, {})
        attempted = int(d.get('port_scan_attempted', 0) or 0)
        ps_success = int(d.get('port_scan_success', 0) or 0)
        open_ports_total = int(d.get('open_ports_total', 0) or 0)
        endpoints_total = int(d.get('endpoints_total', 0) or 0)
        endpoints_passed = int(d.get('endpoints_passed', 0) or 0)

        for port, cnt in (d.get('open_port_counts') or {}).items():
            all_open_ports[port] += cnt

        diag_per_model[ms] = {
            'apps_with_any_output': int(d.get('apps_with_any_output', 0) or 0),
            'port_scan_attempted': attempted,
            'port_scan_success': ps_success,
            'apps_with_open_ports': int(d.get('apps_with_open_ports', 0) or 0),
            'avg_open_ports_per_app': (open_ports_total / ps_success) if ps_success > 0 else 0,
            'curl_attempted': int(d.get('curl_attempted', 0) or 0),
            'curl_success': int(d.get('curl_success', 0) or 0),
            'endpoints_total': endpoints_total,
            'endpoints_passed': endpoints_passed,
            'endpoint_pass_rate': (endpoints_passed / endpoints_total * 100) if endpoints_total > 0 else 0,
        }

    output['dynamic_diagnostics'] = {
        'per_model': diag_per_model,
        'top_open_ports': dict(sorted(all_open_ports.items(), key=lambda x: -x[1])[:15]),
        'total_port_scan_attempted': sum(int(d.get('port_scan_attempted', 0) or 0) for d in dyn_diag_model.values()),
        'total_port_scan_success': sum(int(d.get('port_scan_success', 0) or 0) for d in dyn_diag_model.values()),
        'total_open_ports': sum(int(d.get('open_ports_total', 0) or 0) for d in dyn_diag_model.values()),
        'total_curl_attempted': sum(int(d.get('curl_attempted', 0) or 0) for d in dyn_diag_model.values()),
        'total_endpoints': sum(int(d.get('endpoints_total', 0) or 0) for d in dyn_diag_model.values()),
        'total_endpoints_passed': sum(int(d.get('endpoints_passed', 0) or 0) for d in dyn_diag_model.values()),
    }

    # Performance
    perf_output = {}
    for ms in MODEL_SHORT_NAMES:
        pd = perf_model.get(ms, {'backend_rps': [], 'backend_rt': [], 'tests': 0})
        if pd['backend_rps']:
            perf_output[ms] = {
                'tests': pd['tests'],
                **{f'backend_{k}': v for k, v in _safe_stats(pd['backend_rps']).items()
                   if k != 'n'},
                'backend_rt': _safe_stats(pd['backend_rt']),
            }
        else:
            perf_output[ms] = None
    output['performance'] = perf_output

    # AI compliance
    ai_output = {}
    for ms in MODEL_SHORT_NAMES:
        ad = ai_model.get(ms, {'overall': [], 'backend': [], 'frontend': [], 'admin': [], 'apps': 0})
        if ad['apps'] > 0:
            ai_output[ms] = {
                'apps': ad['apps'],
                'overall': _safe_stats(ad['overall']),
                'backend': _safe_stats(ad['backend']),
                'frontend': _safe_stats(ad['frontend']),
                'admin': _safe_stats(ad['admin']),
            }
        else:
            ai_output[ms] = None
    output['ai_compliance'] = ai_output

    # Performance tools (per-tool per-model metrics)
    perf_tools_output = {}
    for tool_name in sorted(perf_tool_model.keys()):
        tool_data = perf_tool_model[tool_name]
        per_model = {}
        total_runs = 0
        all_rps = []
        all_rt = []
        all_errors = []
        for ms in MODEL_SHORT_NAMES:
            ptm = tool_data.get(ms)
            if ptm and ptm['runs'] > 0:
                per_model[ms] = {
                    'runs': ptm['runs'],
                    'rps': _safe_stats(ptm['rps']),
                    'avg_response_time': _safe_stats(ptm['avg_rt']),
                    'total_requests': sum(ptm['requests']),
                    'total_errors': sum(ptm['errors']),
                    'error_rate': (sum(ptm['errors']) / sum(ptm['requests']) * 100
                                   if sum(ptm['requests']) > 0 else 0),
                }
                if ptm['p95_rt']:
                    per_model[ms]['p95_response_time'] = _safe_stats(ptm['p95_rt'])
                total_runs += ptm['runs']
                all_rps.extend(ptm['rps'])
                all_rt.extend(ptm['avg_rt'])
                all_errors.extend(ptm['errors'])
            else:
                per_model[ms] = None
        perf_tools_output[tool_name] = {
            'total_runs': total_runs,
            'overall_rps': _safe_stats(all_rps),
            'overall_avg_rt': _safe_stats(all_rt),
            'per_model': per_model,
        }
    output['performance_tools'] = perf_tools_output

    # AI tools (per-tool per-model metrics)
    ai_tools_output = {}
    for tool_name in sorted(ai_tool_model.keys()):
        tool_data = ai_tool_model[tool_name]
        per_model = {}
        total_runs = 0
        all_scores = []
        all_grades = []
        for ms in MODEL_SHORT_NAMES:
            atm = tool_data.get(ms)
            if atm and atm['runs'] > 0:
                pm = {
                    'runs': atm['runs'],
                    'score': _safe_stats(atm['scores']),
                    'compliance_pct': _safe_stats(atm['compliance_pcts']),
                }
                if atm['grades']:
                    pm['grades'] = atm['grades']
                    # Most common grade
                    from collections import Counter
                    gc = Counter(atm['grades'])
                    pm['dominant_grade'] = gc.most_common(1)[0][0]
                if atm['metrics_passed'] and atm['metrics_total']:
                    pm['avg_metrics_passed'] = statistics.mean(atm['metrics_passed'])
                    pm['avg_metrics_total'] = statistics.mean(atm['metrics_total'])
                per_model[ms] = pm
                total_runs += atm['runs']
                all_scores.extend(atm['scores'])
                all_grades.extend(atm['grades'])
            else:
                per_model[ms] = None
        ai_tools_out = {
            'total_runs': total_runs,
            'overall_score': _safe_stats(all_scores),
            'per_model': per_model,
        }
        if all_grades:
            from collections import Counter
            gc = Counter(all_grades)
            ai_tools_out['grade_distribution'] = dict(gc.most_common())
        ai_tools_output[tool_name] = ai_tools_out
    output['ai_tools'] = ai_tools_output

    # Dynamic tools (per-tool per-model with findings/runs)
    dynamic_tool_names = ['zap', 'nmap', 'curl', 'curl-endpoint-tester',
                          'connectivity', 'port-scan']
    dyn_tools_output = {}
    for tn in dynamic_tool_names:
        if tn not in tool_model:
            continue
        tm = tool_model[tn]
        total_f = sum(d['findings'] for d in tm.values())
        total_r = sum(d['runs'] for d in tm.values())
        total_sev = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
        per_model = {}
        for ms in MODEL_SHORT_NAMES:
            d = tm.get(ms, {'runs': 0, 'findings': 0,
                            'severity': {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}})
            per_model[ms] = {
                'runs': d['runs'],
                'findings': d['findings'],
                'avg_per_run': d['findings'] / d['runs'] if d['runs'] > 0 else 0,
                'severity': d['severity'],
            }
            for sev in total_sev:
                total_sev[sev] += d['severity'].get(sev, 0)
        dyn_tools_output[tn] = {
            'total_findings': total_f,
            'total_runs': total_r,
            'avg_per_run': total_f / total_r if total_r > 0 else 0,
            'severity': total_sev,
            'per_model': per_model,
        }
    output['dynamic_tools'] = dyn_tools_output

    # Model summary
    model_summary = {}
    for ms in MODEL_SHORT_NAMES:
        app_findings = list(model_app_findings[ms].values())
        total_f = sum(app_findings)
        total_loc = loc_data.get(ms, {}).get('total', 0)
        total_sev = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
        for app_sev in model_app_severity[ms].values():
            for s, c in app_sev.items():
                total_sev[s] += c
        model_summary[ms] = {
            'short_name': MODEL_SHORT_NAMES[ms],
            'total_findings': total_f,
            'total_loc': total_loc,
            'python_loc': loc_data.get(ms, {}).get('python', 0),
            'js_loc': loc_data.get(ms, {}).get('javascript', 0) + loc_data.get(ms, {}).get('jsx', 0),
            'defect_density_kloc': (total_f / total_loc * 1000) if total_loc > 0 else 0,
            'severity': total_sev,
            'stats': _safe_stats(app_findings),
        }
    output['model_summary'] = model_summary

    return output


def print_summary(output: dict) -> None:
    """Print human-readable summary to stdout."""
    ov = output['overview']
    print(f"\n{'='*80}")
    print(
        f"THESIS DATA EXTRACTION — {ov['total_apps']} apps on disk "
        f"({ov.get('apps_with_results', 0)} with results), {ov['total_models']} models"
    )
    print(f"{'='*80}")
    print(f"Static findings: {ov['total_static_findings']:,}")
    print(f"ZAP alerts:      {ov['total_zap_alerts']}")
    for svc, d in ov['service_completion'].items():
        pct = d['success'] / d['total'] * 100 if d['total'] > 0 else 0
        print(f"  {svc:12s}: {d['success']}/{d['total']} ({pct:.0f}%)")

    print(f"\nStatic Tools ({len(output['static_tools'])} tools):")
    for tn, td in sorted(output['static_tools'].items(),
                          key=lambda x: -x[1]['total_findings']):
        if td['total_findings'] > 0:
            s = td['severity']
            print(f"  {tn:20s}: {td['total_findings']:6,d} "
                  f"({td['avg_per_run']:.1f}/run) "
                  f"H={s['high']} M={s['medium']} L={s['low']}")

    # Dynamic tools summary
    dyn_tools = output.get('dynamic_tools', {})
    if dyn_tools:
        print(f"\nDynamic Tools ({len(dyn_tools)} tools):")
        for tn, td in sorted(dyn_tools.items(), key=lambda x: -x[1]['total_findings']):
            print(f"  {tn:24s}: {td['total_runs']:4d} runs, "
                  f"{td['total_findings']:6,d} findings")

    # Performance tools summary
    perf_tools = output.get('performance_tools', {})
    if perf_tools:
        print(f"\nPerformance Tools ({len(perf_tools)} tools):")
        for tn, td in sorted(perf_tools.items()):
            rps = td['overall_rps']
            rt = td['overall_avg_rt']
            print(f"  {tn:12s}: {td['total_runs']:4d} runs, "
                  f"RPS mean={rps['mean']:.1f}, RT mean={rt['mean']:.1f}ms")

    # AI tools summary
    ai_tools = output.get('ai_tools', {})
    if ai_tools:
        print(f"\nAI Analysis Tools ({len(ai_tools)} tools):")
        for tn, td in sorted(ai_tools.items()):
            score = td['overall_score']
            grades = td.get('grade_distribution', {})
            grade_str = ', '.join(f"{g}={c}" for g, c in
                                  sorted(grades.items())) if grades else 'N/A'
            print(f"  {tn:24s}: {td['total_runs']:4d} runs, "
                  f"score mean={score['mean']:.1f}, grades: {grade_str}")

    print(f"\nModel Summary:")
    hdr = f"  {'Model':22s} {'Findings':>8s} {'LOC':>7s} {'D/KLOC':>7s}"
    print(hdr)
    for ms in MODEL_SHORT_NAMES:
        d = output['model_summary'][ms]
        print(f"  {d['short_name']:22s} {d['total_findings']:8,d} "
              f"{d['total_loc']:7,d} {d['defect_density_kloc']:7.1f}")


def main() -> None:
    parser = argparse.ArgumentParser(description='Extract thesis data from results')
    parser.add_argument('--output', '-o', default='thesis_data.json',
                        help='Output JSON file path')
    parser.add_argument('--results-dir', default='results',
                        help='Path to results directory')
    parser.add_argument('--gen-dir', default='generated/apps',
                        help='Path to generated apps directory')
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    gen_dir = Path(args.gen_dir)

    if not results_dir.exists():
        print(f"ERROR: Results directory not found: {results_dir}")
        return

    output = extract_all_data(results_dir, gen_dir)
    with open(args.output, 'w') as f:
        json.dump(output, f, indent=2, default=str)

    print_summary(output)
    print(f"\nFull data saved to: {args.output}")


if __name__ == '__main__':
    main()
