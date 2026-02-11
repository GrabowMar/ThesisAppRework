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
    ai_model = defaultdict(lambda: {'overall': [], 'backend': [], 'frontend': [],
                                     'admin': [], 'apps': 0})
    zap_model = defaultdict(lambda: {'alerts': 0, 'scans': 0,
                                      'by_risk': defaultdict(int),
                                      'cwes': defaultdict(int),
                                      'alert_types': defaultdict(int)})
    service_completion = defaultdict(lambda: {'success': 0, 'total': 0})
    app_count = 0

    for model_dir in sorted(results_dir.iterdir()):
        if not model_dir.is_dir():
            continue
        model_slug = model_dir.name
        for app_dir in sorted(model_dir.iterdir()):
            if not app_dir.is_dir():
                continue
            app_n = app_dir.name
            app_count += 1
            for task_dir in app_dir.iterdir():
                if not task_dir.is_dir():
                    continue
                for f in task_dir.iterdir():
                    if f.name == 'manifest.json' or not f.name.endswith('.json'):
                        continue
                    try:
                        data = json.loads(f.read_text())
                    except Exception:
                        continue
                    services = data.get('services', {})
                    _process_static(services, model_slug, app_n, tool_model,
                                    model_app_findings, model_app_severity, service_completion)
                    _process_dynamic(services, model_slug, zap_model, service_completion)
                    _process_performance(services, model_slug, perf_model, service_completion)
                    _process_ai(services, model_slug, ai_model, service_completion)

    loc_data = count_loc(gen_dir) if gen_dir.exists() else {}
    return _build_output(tool_model, model_app_findings, model_app_severity,
                         perf_model, ai_model, zap_model, service_completion,
                         loc_data, app_count)


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


def _process_dynamic(services: dict, model_slug: str,
                      zap_model: dict, service_completion: dict) -> None:
    dyn = services.get('dynamic-analyzer', {})
    service_completion['dynamic']['total'] += 1
    if dyn.get('status') != 'success':
        return
    service_completion['dynamic']['success'] += 1
    analysis = dyn.get('payload', {}).get('analysis', {})
    results = analysis.get('results', {})
    zap = results.get('zap_security_scan')
    scans = zap if isinstance(zap, list) else ([zap] if isinstance(zap, dict) else [])
    for scan in scans:
        if not isinstance(scan, dict) or scan.get('total_alerts', 0) == 0:
            continue
        zap_model[model_slug]['scans'] += 1
        zap_model[model_slug]['alerts'] += scan['total_alerts']
        for risk, alerts in scan.get('alerts_by_risk', {}).items():
            if isinstance(alerts, list):
                zap_model[model_slug]['by_risk'][risk.lower()] += len(alerts)
                for a in alerts:
                    cwe = a.get('cweid', '')
                    if cwe and cwe != '-1':
                        zap_model[model_slug]['cwes'][f"CWE-{cwe}"] += 1
                    alert_name = a.get('alert', a.get('name', 'Unknown'))
                    zap_model[model_slug]['alert_types'][alert_name] += 1


def _process_performance(services: dict, model_slug: str,
                          perf_model: dict, service_completion: dict) -> None:
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


def _process_ai(services: dict, model_slug: str,
                 ai_model: dict, service_completion: dict) -> None:
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
                   perf_model, ai_model, zap_model, service_completion,
                   loc_data, app_count) -> dict:
    output = {}

    # Overview
    total_static = sum(
        sum(d['findings'] for d in tm.values())
        for tm in tool_model.values()
    )
    total_zap = sum(z['alerts'] for z in zap_model.values())
    output['overview'] = {
        'total_apps': app_count,
        'total_models': len(MODEL_SHORT_NAMES),
        'total_static_findings': total_static,
        'total_zap_alerts': total_zap,
        'service_completion': {k: dict(v) for k, v in service_completion.items()},
    }

    # Static tools
    tool_tables = {}
    for tn in sorted(tool_model.keys()):
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
        z = zap_model.get(ms, {'alerts': 0, 'scans': 0, 'by_risk': {}, 'cwes': {}, 'alert_types': {}})
        zap_output[ms] = {
            'scans': z['scans'], 'alerts': z['alerts'],
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
    print(f"THESIS DATA EXTRACTION — {ov['total_apps']} apps, {ov['total_models']} models")
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
