#!/usr/bin/env python3
"""Generate LaTeX tables for thesis chapter 7 from thesis_data.json.

Each tool type gets customized columns:
- Static/dynamic finding tools: Runs, OK, Findings, Avg/Run, F/kLOC
- Performance tools: Runs, Avg RPS, Avg RT (ms), Err%, Median RT (ms)
- AI tools: Runs, Avg Score, Grade, Compliance%, Metrics Pass%
- Diagnostic tools (nmap, connectivity, port-scan): Runs, Executed, Status columns

Usage:
    python3 scripts/generate_thesis_tables.py [-i thesis_data.json] [-o reports/thesis_tables.tex]
"""
import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Short display names (order matters for tables)
MODEL_ORDER = [
    'openai_gpt-4o-mini',
    'openai_gpt-5.2-codex-20260114',
    'google_gemini-3-pro-preview-20251117',
    'deepseek_deepseek-r1-0528',
    'qwen_qwen3-coder-plus',
    'z-ai_glm-4.7-20251222',
    'mistralai_mistral-small-3.1-24b-instruct-2503',
    'google_gemini-3-flash-preview-20251217',
    'meta-llama_llama-3.1-405b-instruct',
    'anthropic_claude-4.5-sonnet-20250929',
]

SHORT_NAMES = {
    'openai_gpt-4o-mini': 'GPT-4o Mini',
    'openai_gpt-5.2-codex-20260114': 'GPT-5.2 Codex',
    'google_gemini-3-pro-preview-20251117': 'Gemini 3 Pro',
    'deepseek_deepseek-r1-0528': 'DeepSeek R1',
    'qwen_qwen3-coder-plus': 'Qwen3 Coder+',
    'z-ai_glm-4.7-20251222': 'GLM-4.7',
    'mistralai_mistral-small-3.1-24b-instruct-2503': 'Mistral Small 3.1',
    'google_gemini-3-flash-preview-20251217': 'Gemini 3 Flash',
    'meta-llama_llama-3.1-405b-instruct': 'Llama 3.1 405B',
    'anthropic_claude-4.5-sonnet-20250929': 'Claude 4.5 Sonnet',
}

# Model pricing info for TOPSIS/WSM
MODEL_PARAMS = {
    'openai_gpt-4o-mini': {'ctx_k': 128, 'max_out_k': 16, 'in_price': 0.15, 'out_price': 0.60},
    'openai_gpt-5.2-codex-20260114': {'ctx_k': 400, 'max_out_k': 128, 'in_price': 1.75, 'out_price': 14.00},
    'google_gemini-3-pro-preview-20251117': {'ctx_k': 1048, 'max_out_k': 65, 'in_price': 2.00, 'out_price': 12.00},
    'deepseek_deepseek-r1-0528': {'ctx_k': 163, 'max_out_k': 65, 'in_price': 0.40, 'out_price': 1.75},
    'qwen_qwen3-coder-plus': {'ctx_k': 128, 'max_out_k': 65, 'in_price': 1.00, 'out_price': 5.00},
    'z-ai_glm-4.7-20251222': {'ctx_k': 202, 'max_out_k': 65, 'in_price': 0.40, 'out_price': 1.50},
    'mistralai_mistral-small-3.1-24b-instruct-2503': {'ctx_k': 131, 'max_out_k': 131, 'in_price': 0.03, 'out_price': 0.11},
    'google_gemini-3-flash-preview-20251217': {'ctx_k': 1048, 'max_out_k': 65, 'in_price': 0.50, 'out_price': 3.00},
    'meta-llama_llama-3.1-405b-instruct': {'ctx_k': 10, 'max_out_k': 0, 'in_price': 4.00, 'out_price': 4.00},
    'anthropic_claude-4.5-sonnet-20250929': {'ctx_k': 1000, 'max_out_k': 64, 'in_price': 3.00, 'out_price': 15.00},
}


def _get_deploy_pcts(data: dict) -> dict:
    """Return {model_slug: deploy_pct}.

    ab runs backend + frontend per app (2 runs per deployed app),
    so deployed_apps = ab_runs / 2 and Deploy% = deployed_apps / 20 * 100.
    """
    result = {}
    ab_per_model = data.get('performance_tools', {}).get('ab', {}).get('per_model', {})
    for ms in MODEL_ORDER:
        d = ab_per_model.get(ms)
        result[ms] = (d['runs'] / 2 / 20 * 100) if d else 0.0
    return result


def _get_compl_pcts(data: dict) -> dict:
    """Return {model_slug: compliance_pct} from requirements-scanner AI tool."""
    result = {}
    rs_per_model = data.get('ai_tools', {}).get('requirements-scanner', {}).get('per_model', {})
    for ms in MODEL_ORDER:
        d = rs_per_model.get(ms)
        result[ms] = d['compliance_pct']['mean'] if d else 0.0
    return result


def _get_quality_scores(data: dict) -> dict:
    """Return {model_slug: quality_score} from code-quality-analyzer AI tool."""
    result = {}
    cq_per_model = data.get('ai_tools', {}).get('code-quality-analyzer', {}).get('per_model', {})
    for ms in MODEL_ORDER:
        d = cq_per_model.get(ms)
        result[ms] = d['score']['mean'] if d else 0.0
    return result


def _latex_int(n: int | float) -> str:
    """Format integer with LaTeX thousands separator."""
    n = int(n)
    if n >= 1000:
        s = f"{n:,d}"
        return s.replace(',', '{,}')
    return str(n)


def _latex_float(n: float, decimals: int = 2) -> str:
    """Format float for LaTeX."""
    if n == 0:
        return '0' + ('.' + '0' * decimals if decimals > 0 else '')
    return f"{n:.{decimals}f}"


def _sn(slug: str) -> str:
    """Short name for model slug."""
    return SHORT_NAMES.get(slug, slug)


def _sort_models_by(data: dict, key: str, reverse: bool = True) -> list:
    """Sort models by a metric, returning list of (slug, model_data)."""
    items = []
    for ms in MODEL_ORDER:
        d = data.get(ms)
        if d is None:
            items.append((ms, d, 0))
        else:
            val = d.get(key, 0) if isinstance(d, dict) else 0
            items.append((ms, d, val))
    items.sort(key=lambda x: x[2], reverse=reverse)
    return [(slug, d) for slug, d, _ in items]


# ─── Static / Dynamic finding-based tool table ────────────────────────────────

def _gen_findings_tool_table(tool_name: str, tool_data: dict, loc_data: dict,
                              caption: str, label: str, note: str = '') -> str:
    """Generate table for tools that produce findings (static + dynamic finding tools).

    Includes High/Med./Low severity columns when severity data is present.
    Tools with only one severity bucket (e.g. detect-secrets with all zeros,
    or tools whose data has no non-zero high/med/low) get the short 6-column format.
    """
    per_model = tool_data['per_model']

    # Sort by findings desc
    rows = _sort_models_by(per_model, 'findings', reverse=True)

    # Check whether any model has non-trivial severity data
    has_sev = any(
        (md or {}).get('severity', {})
        for _, md in rows
    )

    lines = []
    lines.append(r'\begin{table}[htbp]')
    lines.append(r'    \centering')
    lines.append(f'    \\caption{{{caption}}}')
    lines.append(f'    \\label{{{label}}}')
    lines.append(r'    \small')
    lines.append(r'    \setlength{\tabcolsep}{4pt}')

    if has_sev:
        lines.append(r'    \begin{tabular}{@{} l r r r r r r r r @{}}')
        lines.append(r'        \toprule')
        lines.append(r'        \textbf{Model} & \textbf{Runs} & \textbf{OK} & \textbf{Findings} & \textbf{Avg/Run} & \textbf{F/kLOC} & \textbf{High} & \textbf{Med.} & \textbf{Low} \\')
    else:
        lines.append(r'    \begin{tabular}{@{} l r r r r r @{}}')
        lines.append(r'        \toprule')
        lines.append(r'        \textbf{Model} & \textbf{Runs} & \textbf{OK} & \textbf{Findings} & \textbf{Avg/Run} & \textbf{F/kLOC} \\')
    lines.append(r'        \midrule')

    total_high = total_med = total_low = 0

    for ms, md in rows:
        if md is None:
            md = {'runs': 0, 'findings': 0, 'avg_per_run': 0, 'severity': {}}
        runs = md.get('runs', 0)
        findings = md.get('findings', 0)
        avg = md.get('avg_per_run', 0)
        ok = runs
        total_loc = loc_data.get(ms, {}).get('total_loc', 0) if isinstance(loc_data, dict) else 0
        fkloc = (findings / total_loc * 1000) if total_loc > 0 else 0
        sev = md.get('severity', {})
        high = sev.get('high', 0) + sev.get('critical', 0)
        med = sev.get('medium', 0)
        low = sev.get('low', 0)
        total_high += high
        total_med += med
        total_low += low

        if has_sev:
            lines.append(
                f'        {_sn(ms)} & {runs} & {ok} & '
                f'{_latex_int(findings)} & {_latex_float(avg)} & {_latex_float(fkloc)} & '
                f'{_latex_int(high)} & {_latex_int(med)} & {_latex_int(low)} \\\\'
            )
        else:
            lines.append(
                f'        {_sn(ms)} & {runs} & {ok} & '
                f'{_latex_int(findings)} & {_latex_float(avg)} & {_latex_float(fkloc)} \\\\'
            )

    total_findings = tool_data.get('total_findings', 0)
    lines.append(r'        \midrule')
    if has_sev:
        lines.append(
            f'        \\textbf{{Total}} & --- & --- & \\textbf{{{_latex_int(total_findings)}}} & --- & --- & '
            f'\\textbf{{{_latex_int(total_high)}}} & \\textbf{{{_latex_int(total_med)}}} & \\textbf{{{_latex_int(total_low)}}} \\\\'
        )
    else:
        lines.append(f'        \\textbf{{Total}} & --- & --- & \\textbf{{{_latex_int(total_findings)}}} & --- & --- \\\\')
    lines.append(r'        \bottomrule')
    lines.append(r'    \end{tabular}')
    lines.append(r'    \source{Own elaboration}')
    if note:
        lines.append(f'    \\par\\smallskip{{\\footnotesize\\textit{{Note: {note}}}}}')
    lines.append(r'\end{table}')

    return '\n'.join(lines)


# ─── Performance tool table ───────────────────────────────────────────────────

def _gen_perf_tool_table(tool_name: str, tool_data: dict,
                          caption: str, label: str, note: str = '') -> str:
    """Generate table for performance tools with RPS/RT/error metrics."""
    per_model = tool_data['per_model']
    
    lines = []
    lines.append(r'\begin{table}[htbp]')
    lines.append(r'    \centering')
    lines.append(f'    \\caption{{{caption}}}')
    lines.append(f'    \\label{{{label}}}')
    lines.append(r'    \small')
    lines.append(r'    \begin{tabular}{@{} l r r r r r @{}}')
    lines.append(r'        \toprule')
    lines.append(r'        \textbf{Model} & \textbf{Runs} & \textbf{Avg RPS} & \textbf{Avg RT (ms)} & \textbf{Requests} & \textbf{Errors} \\')
    lines.append(r'        \midrule')
    
    # Sort by runs desc (coverage)
    items = []
    for ms in MODEL_ORDER:
        d = per_model.get(ms)
        items.append((ms, d))
    items.sort(key=lambda x: (x[1] or {}).get('runs', 0), reverse=True)
    
    total_runs = 0
    total_requests = 0
    total_errors = 0
    
    for ms, md in items:
        if md is None:
            lines.append(f'        {_sn(ms)} & 0 & --- & --- & --- & --- \\\\')
            continue
        runs = md.get('runs', 0)
        rps_mean = md.get('rps', {}).get('mean', 0)
        rt_mean = md.get('avg_response_time', {}).get('mean', 0)
        requests = int(md.get('total_requests', 0))
        errors = int(md.get('total_errors', 0))
        
        total_runs += runs
        total_requests += requests
        total_errors += errors
        
        rps_str = _latex_float(rps_mean, 1) if rps_mean > 0 else '---'
        rt_str = _latex_float(rt_mean, 2) if rt_mean > 0 else '---'
        
        lines.append(
            f'        {_sn(ms)} & {runs} & {rps_str} & '
            f'{rt_str} & {_latex_int(requests)} & {_latex_int(errors)} \\\\'
        )
    
    lines.append(r'        \midrule')
    overall_rps = tool_data.get('overall_rps', {}).get('mean', 0)
    overall_rt = tool_data.get('overall_avg_rt', {}).get('mean', 0)
    lines.append(
        f'        \\textbf{{Total}} & {total_runs} & '
        f'{_latex_float(overall_rps, 1)} & {_latex_float(overall_rt, 2)} & '
        f'{_latex_int(total_requests)} & {_latex_int(total_errors)} \\\\'
    )
    lines.append(r'        \bottomrule')
    lines.append(r'    \end{tabular}')
    lines.append(r'    \source{Own elaboration}')
    if note:
        lines.append(f'    \\par\\smallskip{{\\footnotesize\\textit{{Note: {note}}}}}')
    lines.append(r'\end{table}')

    return '\n'.join(lines)


# ─── AI tool table ────────────────────────────────────────────────────────────

def _gen_ai_tool_table(tool_name: str, tool_data: dict,
                        caption: str, label: str, note: str = '') -> str:
    """Generate table for AI analysis tools with score/grade/compliance."""
    per_model = tool_data['per_model']
    
    lines = []
    lines.append(r'\begin{table}[htbp]')
    lines.append(r'    \centering')
    lines.append(f'    \\caption{{{caption}}}')
    lines.append(f'    \\label{{{label}}}')
    lines.append(r'    \small')
    
    if tool_name == 'code-quality-analyzer':
        lines.append(r'    \begin{tabular}{@{} l r r r r r @{}}')
        lines.append(r'        \toprule')
        lines.append(r'        \textbf{Model} & \textbf{Runs} & \textbf{Avg Score} & \textbf{Grade} & \textbf{Compl.\%} & \textbf{Pass/Total} \\')
        lines.append(r'        \midrule')
        
        items = []
        for ms in MODEL_ORDER:
            d = per_model.get(ms)
            items.append((ms, d))
        items.sort(key=lambda x: (x[1] or {}).get('score', {}).get('mean', 0), reverse=True)
        
        for ms, md in items:
            if md is None:
                lines.append(f'        {_sn(ms)} & 0 & --- & --- & --- & --- \\\\')
                continue
            runs = md.get('runs', 0)
            score = md.get('score', {}).get('mean', 0)
            grade = md.get('dominant_grade', '---')
            compl = md.get('compliance_pct', {}).get('mean', 0)
            mp = md.get('avg_metrics_passed', 0)
            mt = md.get('avg_metrics_total', 0)
            pass_total = f'{mp:.0f}/{mt:.0f}' if mt > 0 else '---'
            
            lines.append(
                f'        {_sn(ms)} & {runs} & {_latex_float(score, 1)} & '
                f'{grade} & {_latex_float(compl, 1)} & {pass_total} \\\\'
            )
        
        overall = tool_data.get('overall_score', {}).get('mean', 0)
        grades = tool_data.get('grade_distribution', {})
        grade_str = '/'.join(f'{g}:{c}' for g, c in sorted(grades.items()))
        lines.append(r'        \midrule')
        lines.append(
            f'        \\textbf{{Overall}} & {tool_data.get("total_runs", 0)} & '
            f'{_latex_float(overall, 1)} & {grade_str} & --- & --- \\\\'
        )
    else:
        # requirements-scanner
        lines.append(r'    \begin{tabular}{@{} l r r r r r @{}}')
        lines.append(r'        \toprule')
        lines.append(r'        \textbf{Model} & \textbf{Runs} & \textbf{Avg Compl.\%} & \textbf{Min\%} & \textbf{Max\%} & \textbf{Std} \\')
        lines.append(r'        \midrule')
        
        items = []
        for ms in MODEL_ORDER:
            d = per_model.get(ms)
            items.append((ms, d))
        items.sort(key=lambda x: (x[1] or {}).get('compliance_pct', {}).get('mean', 0), reverse=True)
        
        for ms, md in items:
            if md is None:
                lines.append(f'        {_sn(ms)} & 0 & --- & --- & --- & --- \\\\')
                continue
            runs = md.get('runs', 0)
            compl = md.get('compliance_pct', {})
            mean = compl.get('mean', 0)
            mn = compl.get('min', 0)
            mx = compl.get('max', 0)
            std = compl.get('std', 0)
            
            lines.append(
                f'        {_sn(ms)} & {runs} & {_latex_float(mean, 1)} & '
                f'{_latex_float(mn, 1)} & {_latex_float(mx, 1)} & {_latex_float(std, 1)} \\\\'
            )
        
        overall = tool_data.get('overall_score', {}).get('mean', 0)
        lines.append(r'        \midrule')
        lines.append(
            f'        \\textbf{{Overall}} & {tool_data.get("total_runs", 0)} & '
            f'{_latex_float(overall, 1)} & --- & --- & --- \\\\'
        )
    
    lines.append(r'        \bottomrule')
    lines.append(r'    \end{tabular}')
    lines.append(r'    \source{Own elaboration}')
    if note:
        lines.append(f'    \\par\\smallskip{{\\footnotesize\\textit{{Note: {note}}}}}')
    lines.append(r'\end{table}')

    return '\n'.join(lines)


# ─── Diagnostic tool table (nmap, connectivity, port-scan) ────────────────────

def _gen_diagnostic_tool_table(tool_name: str, tool_data: dict, diag_data: dict,
                                 caption: str, label: str) -> str:
    """Generate table for diagnostic tools that produce execution status, not findings."""
    per_model = tool_data['per_model']
    diag_per_model = diag_data.get('per_model', {})
    
    lines = []
    lines.append(r'\begin{table}[htbp]')
    lines.append(r'    \centering')
    lines.append(f'    \\caption{{{caption}}}')
    lines.append(f'    \\label{{{label}}}')
    lines.append(r'    \small')
    
    if tool_name == 'nmap':
        lines.append(r'    \begin{tabular}{@{} l r r r l @{}}')
        lines.append(r'        \toprule')
        lines.append(r'        \textbf{Model} & \textbf{Runs} & \textbf{Findings} & \textbf{Issues Found} & \textbf{Result} \\')
        lines.append(r'        \midrule')
        for ms in MODEL_ORDER:
            md = per_model.get(ms, {'runs': 0, 'findings': 0})
            runs = md.get('runs', 0)
            findings = md.get('findings', 0)
            result = 'Clean' if runs > 0 and findings == 0 else ('Issues' if findings > 0 else '---')
            lines.append(
                f'        {_sn(ms)} & {runs} & {findings} & {findings} & {result} \\\\'
            )
        lines.append(r'        \midrule')
        lines.append(f'        \\textbf{{Total}} & {tool_data["total_runs"]} & {tool_data["total_findings"]} & --- & --- \\\\')
    
    elif tool_name == 'port-scan':
        lines.append(r'    \begin{tabular}{@{} l r r r r @{}}')
        lines.append(r'        \toprule')
        lines.append(r'        \textbf{Model} & \textbf{Scans} & \textbf{Successful} & \textbf{Open Ports} & \textbf{Avg Ports/App} \\')
        lines.append(r'        \midrule')
        total_scans = 0
        total_success = 0
        total_ports = 0
        for ms in MODEL_ORDER:
            dd = diag_per_model.get(ms, {})
            scans = int(dd.get('port_scan_attempted', 0))
            success = int(dd.get('port_scan_success', 0))
            avg_ports = dd.get('avg_open_ports_per_app', 0)
            # Reconstruct total open ports
            open_ports = int(avg_ports * success) if success > 0 else 0
            total_scans += scans
            total_success += success
            total_ports += open_ports
            lines.append(
                f'        {_sn(ms)} & {scans} & {success} & {open_ports} & {_latex_float(avg_ports, 1)} \\\\'
            )
        lines.append(r'        \midrule')
        overall_avg = total_ports / total_success if total_success > 0 else 0
        lines.append(
            f'        \\textbf{{Total}} & {total_scans} & {total_success} & '
            f'{total_ports} & {_latex_float(overall_avg, 1)} \\\\'
        )
    
    elif tool_name == 'connectivity':
        lines.append(r'    \begin{tabular}{@{} l r r r @{}}')
        lines.append(r'        \toprule')
        lines.append(r'        \textbf{Model} & \textbf{Apps Checked} & \textbf{With Output} & \textbf{Coverage\%} \\')
        lines.append(r'        \midrule')
        total_checked = 0
        total_output = 0
        for ms in MODEL_ORDER:
            md = per_model.get(ms, {'runs': 0})
            runs = md.get('runs', 0)
            dd = diag_per_model.get(ms, {})
            with_output = int(dd.get('apps_with_any_output', 0))
            coverage = (with_output / runs * 100) if runs > 0 else 0
            total_checked += runs
            total_output += with_output
            lines.append(
                f'        {_sn(ms)} & {runs} & {with_output} & {_latex_float(coverage, 1)} \\\\'
            )
        lines.append(r'        \midrule')
        overall_cov = (total_output / total_checked * 100) if total_checked > 0 else 0
        lines.append(
            f'        \\textbf{{Total}} & {total_checked} & {total_output} & {_latex_float(overall_cov, 1)} \\\\'
        )
    
    lines.append(r'        \bottomrule')
    lines.append(r'    \end{tabular}')
    lines.append(r'    \source{Own elaboration}')
    lines.append(r'\end{table}')
    
    return '\n'.join(lines)


# ─── Service completion table ─────────────────────────────────────────────────

def _gen_service_completion_table(data: dict) -> str:
    """Generate Table: Service Completion Rates."""
    sc = data['overview']['service_completion']
    lines = []
    lines.append(r'\begin{table}[htbp]')
    lines.append(r'    \centering')
    lines.append(r'    \caption{Service Completion Rates Across All Applications}')
    lines.append(r'    \label{tab:service_completion}')
    lines.append(r'    \small')
    lines.append(r'    \begin{tabular}{@{} l r r r r @{}}')
    lines.append(r'        \toprule')
    lines.append(r'        \textbf{Service} & \textbf{Success} & \textbf{Failed} & \textbf{Total} & \textbf{Rate (\%)} \\')
    lines.append(r'        \midrule')
    
    svc_names = {
        'static': 'Static Analyzer',
        'dynamic': 'Dynamic Analyzer',
        'performance': 'Performance Analyzer',
        'ai': 'AI Analyzer',
    }
    for key in ['static', 'dynamic', 'performance', 'ai']:
        d = sc.get(key, {'success': 0, 'total': 0})
        total = d['total']
        success = d['success']
        failed = total - success
        rate = (success / total * 100) if total > 0 else 0
        lines.append(
            f'        {svc_names[key]} & {success} & {failed} & {total} & {_latex_float(rate, 1)} \\\\'
        )
    
    lines.append(r'        \bottomrule')
    lines.append(r'    \end{tabular}')
    lines.append(r'    \source{Own elaboration}')
    lines.append(r'\end{table}')
    return '\n'.join(lines)


# ─── Code composition table ──────────────────────────────────────────────────

def _gen_code_composition_table(data: dict) -> str:
    """Generate Table: Code Composition by Model (with Deploy%)."""
    ms_data = data['model_summary']
    deploy_pcts = _get_deploy_pcts(data)

    items = []
    for ms in MODEL_ORDER:
        d = ms_data.get(ms, {})
        loc_app = d.get('total_loc', 0) / 20
        items.append((ms, d, loc_app))
    items.sort(key=lambda x: x[2], reverse=True)

    lines = []
    lines.append(r'\begin{table}[htbp]')
    lines.append(r'    \centering')
    lines.append(r'    \caption{Code Composition and Deployment Success by Model (Sorted by LOC/App)}')
    lines.append(r'    \label{tab:code_composition}')
    lines.append(r'    \small')
    lines.append(r'    \setlength{\tabcolsep}{4pt}')
    lines.append(r'    \begin{tabular}{@{} l r r r r r r r @{}}')
    lines.append(r'        \toprule')
    lines.append(r'        \textbf{Model} & \textbf{Apps} & \textbf{Total LOC} & \textbf{Python} & \textbf{JS} & \textbf{LOC/App} & \textbf{I/100LOC} & \textbf{Deploy\%} \\')
    lines.append(r'        \midrule')

    for ms, d, loc_app in items:
        apps = 20
        total_loc = d.get('total_loc', 0)
        py_loc = d.get('python_loc', 0)
        js_loc = d.get('js_loc', 0)
        findings = d.get('total_findings', 0)
        i100 = (findings / total_loc * 100) if total_loc > 0 else 0
        deploy_pct = deploy_pcts.get(ms, 0)

        lines.append(
            f'        {_sn(ms)} & {apps} & {_latex_int(total_loc)} & '
            f'{_latex_int(py_loc)} & {_latex_int(js_loc)} & '
            f'{_latex_int(loc_app)} & {_latex_float(i100)} & {_latex_int(deploy_pct)} \\\\'
        )

    lines.append(r'        \bottomrule')
    lines.append(r'    \end{tabular}')
    lines.append(r'    \source{Own elaboration}')
    lines.append(r'\end{table}')
    return '\n'.join(lines)


# ─── Severity table ──────────────────────────────────────────────────────────

def _gen_severity_table(data: dict, note: str = '') -> str:
    """Generate Table: Findings by Severity per Model."""
    ms_data = data['model_summary']
    
    items = []
    for ms in MODEL_ORDER:
        d = ms_data.get(ms, {})
        items.append((ms, d))
    items.sort(key=lambda x: x[1].get('defect_density_kloc', 0), reverse=True)
    
    lines = []
    lines.append(r'\begin{table}[htbp]')
    lines.append(r'    \centering')
    lines.append(r'    \caption{Findings by Severity per Model (D/kLOC = Defects per 1{,}000 Lines of Code; sorted by D/kLOC desc.)}')
    lines.append(r'    \label{tab:severity_model}')
    lines.append(r'    \small')
    lines.append(r'    \setlength{\tabcolsep}{4pt}')
    lines.append(r'    \begin{tabular}{@{} l r r r r r r r @{}}')
    lines.append(r'        \toprule')
    lines.append(r'        \textbf{Model} & \textbf{Critical} & \textbf{High} & \textbf{Medium} & \textbf{Low} & \textbf{Info} & \textbf{Total} & \textbf{D/kLOC} \\')
    lines.append(r'        \midrule')
    
    for ms, d in items:
        sev = d.get('severity', {})
        total = d.get('total_findings', 0)
        dkloc = d.get('defect_density_kloc', 0)
        lines.append(
            f'        {_sn(ms)} & {_latex_int(sev.get("critical", 0))} & '
            f'{_latex_int(sev.get("high", 0))} & {_latex_int(sev.get("medium", 0))} & '
            f'{_latex_int(sev.get("low", 0))} & {_latex_int(sev.get("info", 0))} & '
            f'{_latex_int(total)} & {_latex_float(dkloc, 1)} \\\\'
        )
    
    lines.append(r'        \bottomrule')
    lines.append(r'    \end{tabular}')
    lines.append(r'    \source{Own elaboration}')
    if note:
        lines.append(f'    \\par\\smallskip{{\\footnotesize\\textit{{Note: {note}}}}}')
    lines.append(r'\end{table}')
    return '\n'.join(lines)


# ─── ZAP table ────────────────────────────────────────────────────────────────

def _gen_zap_table(data: dict, note: str = '') -> str:
    """Generate Table: OWASP ZAP Results."""
    zap = data['dynamic_zap']
    per_model = zap['per_model']
    loc_data = data['model_summary']
    
    items = []
    for ms in MODEL_ORDER:
        d = per_model.get(ms, {})
        items.append((ms, d))
    items.sort(key=lambda x: x[1].get('alerts', 0), reverse=True)
    
    lines = []
    lines.append(r'\begin{table}[htbp]')
    lines.append(r'    \centering')
    lines.append(r'    \caption{OWASP ZAP: Dynamic Vulnerability Scanning Results by Model}')
    lines.append(r'    \label{tab:tool_zap}')
    lines.append(r'    \small')
    lines.append(r'    \begin{tabular}{@{} l r r r r r r r @{}}')
    lines.append(r'        \toprule')
    lines.append(r'        \textbf{Model} & \textbf{Scans} & \textbf{Alerts} & \textbf{High} & \textbf{Medium} & \textbf{Low} & \textbf{Info} & \textbf{Avg/Scan} \\')
    lines.append(r'        \midrule')
    
    for ms, d in items:
        scans = d.get('scans', 0)
        alerts = d.get('alerts', 0)
        high = d.get('high', 0)
        medium = d.get('medium', 0)
        low = d.get('low', 0)
        info = d.get('informational', 0)
        avg = alerts / scans if scans > 0 else 0
        lines.append(
            f'        {_sn(ms)} & {scans} & {_latex_int(alerts)} & '
            f'{high} & {medium} & {low} & {info} & {_latex_float(avg, 1)} \\\\'
        )
    
    lines.append(r'        \midrule')
    lines.append(
        f'        \\textbf{{Total}} & {zap["total_scans"]} & '
        f'\\textbf{{{_latex_int(zap["total_alerts"])}}} & --- & --- & --- & --- & --- \\\\'
    )
    lines.append(r'        \bottomrule')
    lines.append(r'    \end{tabular}')
    lines.append(r'    \source{Own elaboration}')
    if note:
        lines.append(f'    \\par\\smallskip{{\\footnotesize\\textit{{Note: {note}}}}}')
    lines.append(r'\end{table}')
    return '\n'.join(lines)


# ─── Curl endpoint tester table ───────────────────────────────────────────────

def _gen_curl_endpoint_table(data: dict) -> str:
    """Generate Table: Curl Endpoint Tester Results."""
    diag = data['dynamic_diagnostics']
    diag_pm = diag['per_model']
    dt = data['dynamic_tools'].get('curl-endpoint-tester', {})
    dt_pm = dt.get('per_model', {})
    
    items = []
    for ms in MODEL_ORDER:
        dd = diag_pm.get(ms, {})
        td = dt_pm.get(ms, {'runs': 0, 'findings': 0})
        items.append((ms, dd, td))
    items.sort(key=lambda x: x[2].get('findings', 0), reverse=True)
    
    lines = []
    lines.append(r'\begin{table}[htbp]')
    lines.append(r'    \centering')
    lines.append(r'    \caption{Curl Endpoint Tester: API Endpoint Validation Results by Model}')
    lines.append(r'    \label{tab:tool_curlendpoint}')
    lines.append(r'    \small')
    lines.append(r'    \begin{tabular}{@{} l r r r r r @{}}')
    lines.append(r'        \toprule')
    lines.append(r'        \textbf{Model} & \textbf{Runs} & \textbf{Endpoints} & \textbf{Passed} & \textbf{Failed} & \textbf{Pass\%} \\')
    lines.append(r'        \midrule')
    
    total_endpoints = 0
    total_passed = 0
    
    for ms, dd, td in items:
        runs = td.get('runs', 0)
        endpoints = int(dd.get('endpoints_total', 0))
        passed = int(dd.get('endpoints_passed', 0))
        failed = endpoints - passed
        pass_rate = dd.get('endpoint_pass_rate', 0)
        total_endpoints += endpoints
        total_passed += passed
        lines.append(
            f'        {_sn(ms)} & {runs} & {_latex_int(endpoints)} & '
            f'{_latex_int(passed)} & {_latex_int(failed)} & {_latex_float(pass_rate, 1)} \\\\'
        )
    
    total_rate = (total_passed / total_endpoints * 100) if total_endpoints > 0 else 0
    lines.append(r'        \midrule')
    lines.append(
        f'        \\textbf{{Total}} & --- & {_latex_int(total_endpoints)} & '
        f'{_latex_int(total_passed)} & {_latex_int(total_endpoints - total_passed)} & '
        f'{_latex_float(total_rate, 1)} \\\\'
    )
    lines.append(r'        \bottomrule')
    lines.append(r'    \end{tabular}')
    lines.append(r'    \source{Own elaboration}')
    lines.append(r'\end{table}')
    return '\n'.join(lines)


# ─── Heatmap table ────────────────────────────────────────────────────────────

def _gen_heatmap_table(data: dict) -> str:
    """Generate Tool × Model Findings Heatmap."""
    static = data['static_tools']
    dynamic = data['dynamic_tools']
    
    # Collect tools with nonzero findings
    tools_with_findings = []
    for tn, td in sorted(static.items()):
        if td['total_findings'] > 0:
            tools_with_findings.append((tn, td))
    for tn, td in sorted(dynamic.items()):
        if td['total_findings'] > 0 and tn not in [t[0] for t in tools_with_findings]:
            tools_with_findings.append((tn, td))
    
    lines = []
    lines.append(r'\begin{table}[htbp]')
    lines.append(r'    \centering')
    lines.append(r'    \caption{Tool $\times$ Model Findings Heatmap (Tools With Nonzero Findings; Claude 4.5 Has 50 Apps)}')
    lines.append(r'    \label{tab:heatmap}')
    lines.append(r'    \footnotesize')
    lines.append(r'    \setlength{\tabcolsep}{2.5pt}')
    lines.append(r'    \renewcommand{\arraystretch}{1.05}')
    lines.append(r'    \resizebox{\textwidth}{!}{%')
    
    # Build header
    header_models = ' & '.join(f'\\rotatebox{{70}}{{\\textbf{{{_sn(ms)}}}}}' for ms in MODEL_ORDER)
    n_cols = len(MODEL_ORDER)
    lines.append(f'    \\begin{{tabular}}{{@{{}} l {"r " * n_cols}@{{}}}}')
    lines.append(r'        \toprule')
    lines.append(f'        \\textbf{{Tool}} & {header_models} \\\\')
    lines.append(r'        \midrule')
    
    for tn, td in tools_with_findings:
        pm = td['per_model']
        cells = []
        for ms in MODEL_ORDER:
            md = pm.get(ms, {'findings': 0})
            f = md.get('findings', 0)
            cells.append(_latex_int(f))
        lines.append(f'        {tn} & {" & ".join(cells)} \\\\')
    
    lines.append(r'        \bottomrule')
    lines.append(r'    \end{tabular}%')
    lines.append(r'    }')
    lines.append(r'    \source{Own elaboration}')
    lines.append(r'\end{table}')
    return '\n'.join(lines)


# ─── TOPSIS / WSM tables ─────────────────────────────────────────────────────

def _gen_topsis_table(data: dict, note: str = '') -> str:
    """Generate TOPSIS Multi-Criteria Decision Analysis table.

    Criteria (matching thesis):
      Deploy%   30% benefit
      Compl.%   10% benefit
      Quality   10% benefit
      LOC/App   20% benefit
      D/kLOC    15% cost
      Out$/Mtok 15% cost
    """
    import math
    ms_data = data['model_summary']
    deploy_pcts = _get_deploy_pcts(data)
    compl_pcts = _get_compl_pcts(data)
    quality_scores = _get_quality_scores(data)

    rows = []
    for ms in MODEL_ORDER:
        d = ms_data.get(ms, {})
        total_loc = d.get('total_loc', 0)
        loc_app = total_loc / 20
        dkloc = d.get('defect_density_kloc', 0)
        out_price = MODEL_PARAMS.get(ms, {}).get('out_price', 0)
        rows.append({
            'slug': ms,
            'deploy': deploy_pcts.get(ms, 0),
            'compl': compl_pcts.get(ms, 0),
            'quality': quality_scores.get(ms, 0),
            'loc_app': loc_app,
            'dkloc': dkloc,
            'out_price': out_price,
        })

    criteria = ['deploy', 'compl', 'quality', 'loc_app', 'dkloc', 'out_price']
    weights  = [0.30,    0.10,   0.10,     0.20,     0.15,   0.15]
    is_benefit = [True, True, True, True, False, False]

    # Vector normalisation
    norms = {}
    for c in criteria:
        ss = math.sqrt(sum(r[c]**2 for r in rows))
        norms[c] = ss if ss > 0 else 1

    normalized = [{c: r[c] / norms[c] for c in criteria} for r in rows]
    weighted   = [{c: nr[c] * weights[i] for i, c in enumerate(criteria)} for nr in normalized]

    ideal = {}
    anti_ideal = {}
    for i, c in enumerate(criteria):
        vals = [wr[c] for wr in weighted]
        if is_benefit[i]:
            ideal[c], anti_ideal[c] = max(vals), min(vals)
        else:
            ideal[c], anti_ideal[c] = min(vals), max(vals)

    scores = []
    for wr in weighted:
        d_plus  = math.sqrt(sum((wr[c] - ideal[c])**2     for c in criteria))
        d_minus = math.sqrt(sum((wr[c] - anti_ideal[c])**2 for c in criteria))
        scores.append(d_minus / (d_plus + d_minus) if (d_plus + d_minus) > 0 else 0)

    combined = sorted(zip(rows, scores), key=lambda x: x[1], reverse=True)

    lines = []
    lines.append(r'\begin{table}[htbp]')
    lines.append(r'    \centering')
    lines.append(r'    \caption{TOPSIS Multi-Criteria Decision Analysis (Higher Score = Better)}')
    lines.append(r'    \label{tab:topsis}')
    lines.append(r'    \small')
    lines.append(r'    \setlength{\tabcolsep}{4pt}')
    lines.append(r'    \begin{tabular}{@{} l r r r r r r r r @{}}')
    lines.append(r'        \toprule')
    lines.append(r'        \textbf{Model} & \textbf{Deploy\%} & \textbf{Compl.\%} & \textbf{Quality} & \textbf{LOC/App} & \textbf{D/kLOC} & \textbf{\$/Mtok} & \textbf{Score} & \textbf{Rank} \\')
    lines.append(r'        \midrule')

    for rank, (r, score) in enumerate(combined, 1):
        lines.append(
            f'        {_sn(r["slug"])} & {_latex_int(r["deploy"])} & '
            f'{_latex_float(r["compl"], 1)} & {_latex_float(r["quality"], 1)} & '
            f'{_latex_int(r["loc_app"])} & {_latex_float(r["dkloc"], 1)} & '
            f'{_latex_float(r["out_price"])} & {_latex_float(score, 4)} & {rank} \\\\'
        )

    lines.append(r'        \bottomrule')
    lines.append(r'    \end{tabular}')
    lines.append(r'    \source{Own elaboration}')
    if note:
        lines.append(f'    \\par\\smallskip{{\\footnotesize\\textit{{Note: {note}}}}}')
    lines.append(r'\end{table}')
    return '\n'.join(lines)


def _gen_wsm_table(data: dict, note: str = '') -> str:
    """Generate Weighted Sum Model Ranking table.

    Criteria (matching thesis):
      Deploy%  30% benefit
      Compl.%  30% benefit
      Quality  20% benefit
      D/kLOC   20% cost
    """
    ms_data = data['model_summary']
    deploy_pcts = _get_deploy_pcts(data)
    compl_pcts = _get_compl_pcts(data)
    quality_scores = _get_quality_scores(data)

    rows = []
    for ms in MODEL_ORDER:
        d = ms_data.get(ms, {})
        dkloc = d.get('defect_density_kloc', 0)
        rows.append({
            'slug': ms,
            'deploy': deploy_pcts.get(ms, 0),
            'compl': compl_pcts.get(ms, 0),
            'quality': quality_scores.get(ms, 0),
            'dkloc': dkloc,
        })

    criteria   = ['deploy', 'compl', 'quality', 'dkloc']
    weights    = [0.30,    0.30,   0.20,     0.20]
    is_benefit = [True,    True,   True,     False]

    mins = {c: min(r[c] for r in rows) for c in criteria}
    maxs = {c: max(r[c] for r in rows) for c in criteria}

    scores = []
    for r in rows:
        score = 0.0
        for i, c in enumerate(criteria):
            rng = maxs[c] - mins[c]
            if rng == 0:
                norm = 1.0
            elif is_benefit[i]:
                norm = (r[c] - mins[c]) / rng
            else:
                norm = (maxs[c] - r[c]) / rng
            score += norm * weights[i]
        scores.append(score)

    combined = sorted(zip(rows, scores), key=lambda x: x[1], reverse=True)

    lines = []
    lines.append(r'\begin{table}[htbp]')
    lines.append(r'    \centering')
    lines.append(r'    \caption{Weighted Sum Model Ranking (Higher Score = Better)}')
    lines.append(r'    \label{tab:wsm}')
    lines.append(r'    \small')
    lines.append(r'    \begin{tabular}{@{} l r r r r r r @{}}')
    lines.append(r'        \toprule')
    lines.append(r'        \textbf{Model} & \textbf{Deploy\%} & \textbf{Compl.\%} & \textbf{Quality} & \textbf{D/kLOC} & \textbf{Score} & \textbf{Rank} \\')
    lines.append(r'        \midrule')

    for rank, (r, score) in enumerate(combined, 1):
        lines.append(
            f'        {_sn(r["slug"])} & {_latex_int(r["deploy"])} & '
            f'{_latex_float(r["compl"], 1)} & {_latex_float(r["quality"], 1)} & '
            f'{_latex_float(r["dkloc"], 1)} & {_latex_float(score, 4)} & {rank} \\\\'
        )

    lines.append(r'        \bottomrule')
    lines.append(r'    \end{tabular}')
    lines.append(r'    \source{Own elaboration}')
    if note:
        lines.append(f'    \\par\\smallskip{{\\footnotesize\\textit{{Note: {note}}}}}')
    lines.append(r'\end{table}')
    return '\n'.join(lines)


# ─── Correlation table ────────────────────────────────────────────────────────

def _gen_correlation_table(data: dict, note: str = '') -> str:
    """Generate Spearman Rank Correlation table.

    Outcomes (matching thesis): Deploy%, Total LOC, LOC/App, D/kLOC, Compl.%, Quality
    Parameters: Context (k), Max Out (k), Out $/Mtok
    """
    ms_data = data['model_summary']
    deploy_pcts = _get_deploy_pcts(data)
    compl_pcts = _get_compl_pcts(data)
    quality_scores = _get_quality_scores(data)

    # Gather per-model vectors (in MODEL_ORDER)
    deploys = []
    total_locs = []
    loc_apps = []
    dklocs = []
    compls = []
    qualities = []
    ctx_ks = []
    max_outs = []
    out_prices = []

    for ms in MODEL_ORDER:
        d = ms_data.get(ms, {})
        total_loc = d.get('total_loc', 0)
        total_locs.append(total_loc)
        loc_apps.append(total_loc / 20)
        dklocs.append(d.get('defect_density_kloc', 0))
        deploys.append(deploy_pcts.get(ms, 0))
        compls.append(compl_pcts.get(ms, 0))
        qualities.append(quality_scores.get(ms, 0))
        p = MODEL_PARAMS.get(ms, {})
        ctx_ks.append(p.get('ctx_k', 0))
        max_outs.append(p.get('max_out_k', 0))
        out_prices.append(p.get('out_price', 0))

    def _rank(vals):
        indexed = sorted(enumerate(vals), key=lambda x: x[1])
        ranks = [0.0] * len(vals)
        i = 0
        while i < len(indexed):
            j = i
            while j < len(indexed) - 1 and indexed[j + 1][1] == indexed[j][1]:
                j += 1
            avg_rank = sum(range(i + 1, j + 2)) / (j - i + 1)
            for k in range(i, j + 1):
                ranks[indexed[k][0]] = avg_rank
            i = j + 1
        return ranks

    def _spearman(x, y):
        n = len(x)
        rx = _rank(x)
        ry = _rank(y)
        d2 = sum((rx[i] - ry[i]) ** 2 for i in range(n))
        return 1 - (6 * d2) / (n * (n ** 2 - 1))

    params = [
        ('Context (k)',  ctx_ks),
        ('Max Out (k)',  max_outs),
        ('Out \\$/Mtok', out_prices),
    ]
    outcomes = [
        ('Deploy\\%',  deploys),
        ('Total LOC',  total_locs),
        ('LOC/App',    loc_apps),
        ('D/kLOC',     dklocs),
        ('Compl.\\%',  compls),
        ('Quality',    qualities),
    ]

    n_out = len(outcomes)
    lines = []
    lines.append(r'\begin{table}[htbp]')
    lines.append(r'    \centering')
    lines.append(r'    \caption{Spearman Rank Correlations Between Model Parameters and Study Outcomes ($n = 10$)}')
    lines.append(r'    \label{tab:correlations}')
    lines.append(r'    \small')
    lines.append(r'    \setlength{\tabcolsep}{4pt}')
    lines.append(f'    \\begin{{tabular}}{{@{{}} l {"r " * n_out}@{{}}}}')
    lines.append(r'        \toprule')
    header = ' & '.join(f'\\textbf{{{o[0]}}}' for o in outcomes)
    lines.append(f'        \\textbf{{Parameter}} & {header} \\\\')
    lines.append(r'        \midrule')

    for pname, pvals in params:
        cells = []
        for _, ovals in outcomes:
            rho = _spearman(pvals, ovals)
            sign = '$-$' if rho < 0 else ''
            cells.append(f'{sign}{abs(rho):.2f}')
        lines.append(f'        {pname} & {" & ".join(cells)} \\\\')

    lines.append(r'        \bottomrule')
    lines.append(r'    \end{tabular}')
    lines.append(r'    \source{Own elaboration}')
    if note:
        lines.append(f'    \\par\\smallskip{{\\footnotesize\\textit{{Note: {note}}}}}')
    lines.append(r'\end{table}')
    return '\n'.join(lines)


# ─── Per-model service completion table ───────────────────────────────────────

def _gen_per_model_service_table(data: dict) -> str:
    """Generate per-model service completion table from raw result files."""
    # This requires per-model service data; we'll reconstruct from overview
    # We need per-model data — check if it exists in the data
    sc = data['overview']['service_completion']
    static_tools = data['static_tools']
    perf_tools = data['performance_tools']
    ai_tools = data['ai_tools']
    dynamic = data['dynamic_zap']
    
    lines = []
    lines.append(r'\begin{table}[htbp]')
    lines.append(r'    \centering')
    lines.append(r'    \caption{Per-Model Service Completion (Successful / Total Attempted)}')
    lines.append(r'    \label{tab:model_service}')
    lines.append(r'    \small')
    lines.append(r'    \setlength{\tabcolsep}{4pt}')
    lines.append(r'    \resizebox{\textwidth}{!}{%')
    lines.append(r'    \begin{tabular}{@{} l r r r r r r r r @{}}')
    lines.append(r'        \toprule')
    lines.append(r'        \textbf{Model} & \textbf{Stat.} & \textbf{/ Tot} & \textbf{Dyn.} & \textbf{/ Tot} & \textbf{Perf.} & \textbf{/ Tot} & \textbf{AI} & \textbf{/ Tot} \\')
    lines.append(r'        \midrule')
    
    for ms in MODEL_ORDER:
        apps = 20
        # Static: always succeeds, use first tool's run count
        first_tool = next(iter(static_tools.values()), {})
        stat_runs = first_tool.get('per_model', {}).get(ms, {}).get('runs', 0)
        # Dynamic: use ZAP attempted_scans as proxy
        dyn_data = dynamic.get('per_model', {}).get(ms, {})
        dyn_success = dyn_data.get('scans', 0) + (1 if dyn_data.get('attempted_scans', 0) > dyn_data.get('scans', 0) else 0)
        dyn_success = dyn_data.get('attempted_scans', 0)
        # Better: use dynamic_tools runs
        dyn_tools = data['dynamic_tools']
        dyn_runs = dyn_tools.get('zap', {}).get('per_model', {}).get(ms, {}).get('runs', 0)
        # Performance: use any perf tool
        ab_data = perf_tools.get('ab', {}).get('per_model', {}).get(ms)
        perf_runs = ab_data['runs'] // 2 if ab_data else 0  # Each app has 2 runs (backend+frontend)
        # AI: use requirements-scanner
        ai_data = ai_tools.get('requirements-scanner', {}).get('per_model', {}).get(ms)
        ai_runs = ai_data['runs'] if ai_data else 0
        
        lines.append(
            f'        {_sn(ms)} & {stat_runs} & {apps} & '
            f'{perf_runs} & {apps} & {perf_runs} & {apps} & '
            f'{ai_runs} & {apps} \\\\'
        )
    
    lines.append(r'        \bottomrule')
    lines.append(r'    \end{tabular}%')
    lines.append(r'    }')
    lines.append(r'    \source{Own elaboration}')
    lines.append(r'\end{table}')
    return '\n'.join(lines)


# ─── AI Compliance Summary table ──────────────────────────────────────────────

def _gen_ai_compliance_summary(data: dict, note: str = '') -> str:
    """Generate AI compliance summary (backend/frontend/admin/overall)."""
    ai_compl = data['ai_compliance']
    
    items = []
    for ms in MODEL_ORDER:
        d = ai_compl.get(ms)
        items.append((ms, d))
    items.sort(key=lambda x: (x[1] or {}).get('overall', {}).get('mean', 0), reverse=True)
    
    lines = []
    lines.append(r'\begin{table}[htbp]')
    lines.append(r'    \centering')
    lines.append(r'    \caption{Requirements Compliance Summary by Model (\%)}')
    lines.append(r'    \label{tab:ai_compliance_summary}')
    lines.append(r'    \small')
    lines.append(r'    \begin{tabular}{@{} l r r r r r @{}}')
    lines.append(r'        \toprule')
    lines.append(r'        \textbf{Model} & \textbf{Apps} & \textbf{Overall} & \textbf{Backend} & \textbf{Frontend} & \textbf{Admin} \\')
    lines.append(r'        \midrule')
    
    for ms, d in items:
        if d is None:
            lines.append(f'        {_sn(ms)} & 0 & --- & --- & --- & --- \\\\')
            continue
        apps = d.get('apps', 0)
        overall = d.get('overall', {}).get('mean', 0)
        backend = d.get('backend', {}).get('mean', 0)
        frontend = d.get('frontend', {}).get('mean', 0)
        admin = d.get('admin', {}).get('mean', 0)
        lines.append(
            f'        {_sn(ms)} & {apps} & {_latex_float(overall, 1)} & '
            f'{_latex_float(backend, 1)} & {_latex_float(frontend, 1)} & {_latex_float(admin, 1)} \\\\'
        )
    
    lines.append(r'        \bottomrule')
    lines.append(r'    \end{tabular}')
    lines.append(r'    \source{Own elaboration}')
    if note:
        lines.append(f'    \\par\\smallskip{{\\footnotesize\\textit{{Note: {note}}}}}')
    lines.append(r'\end{table}')
    return '\n'.join(lines)


# ─── Reproducibility tables ──────────────────────────────────────────────────

def _gen_reproducibility_tables(data: dict) -> str:
    """Generate reproducibility tables for Claude 4.5 Sonnet."""
    # These require per-app per-template data which thesis_data.json doesn't have
    # Return a comment indicating manual data needed
    return '% Reproducibility tables require per-app per-template data — generate separately with extract_thesis_data.py --reproducibility flag'


# ─── Main assembly ────────────────────────────────────────────────────────────

def generate_report(data: dict) -> str:
    """Generate the full LaTeX report from thesis_data.json."""
    loc_data = data['model_summary']
    sections = []

    # ── Compute deployment coverage for dynamic/perf notes ──
    _sc = data.get('overview', {}).get('service_completion', {})
    _dyn = _sc.get('dynamic', {})
    _dyn_success = _dyn.get('success', 0)
    _dyn_total = _dyn.get('total', 0)
    _dyn_pct = round(_dyn_success / _dyn_total * 100) if _dyn_total > 0 else 0

    # ── Per-tool notes ──
    _static_tool_notes: dict[str, str] = {
        'detect-secrets': (
            'Zero findings across all models. LLM-generated code contained no '
            'detectable hardcoded secrets under the default ruleset. This is a '
            'legitimate null result, not a measurement failure.'
        ),
        'stylelint': (
            'Zero findings across all models. LLM-generated CSS consistently '
            'passed default stylelint rules. Results may differ under stricter '
            'rule configurations.'
        ),
        'html-validator': (
            '\\textbf{Data unreliable.} The tool was invoked with incorrect '
            'positional file arguments instead of the required '
            '\\texttt{-{}-file=<path>} flag, causing silent failures in all '
            '391 executions. All zero-finding values are an artefact of this '
            'bug and should be disregarded.'
        ),
    }
    _deployed_note = (
        f'Only successfully deployed apps were analysed '
        f'({_dyn_success}/{_dyn_total}, {_dyn_pct}\\%). '
        'Models with zero deployment show zero values because analysis was '
        'impossible, not because their apps were clean.'
    )
    _compliance_penalty_note = (
        'Compliance scores for non-deployed apps were multiplied by 0.70, '
        'reflecting that only static requirements could be verified; dynamic '
        'and interaction requirements were untested for those apps. This '
        'penalty is applied uniformly regardless of the reason for deployment '
        'failure (code error, Docker misconfiguration, etc.).'
    )
    _ranking_note = (
        'The Compl.\\% input includes a 0.70 penalty for non-deployed apps, '
        'which may conflate deployment infrastructure failures with genuine '
        'requirements non-compliance.'
    )
    _corr_note = (
        '$n = 10$ models; Spearman correlations are reported without '
        'significance testing. At this sample size ($n = 10$) most '
        'coefficients would not reach conventional statistical significance '
        '($p < 0.05$), so values should be treated as indicative only.'
    )
    _sev_note = (
        'Three static tools reported zero findings across all models: '
        'stylelint (CSS passes default rules), detect-secrets (no hardcoded '
        'secrets found), and html-validator (invoked with incorrect '
        'arguments---see its individual table). Their zero counts are '
        'included in the totals above.'
    )
    
    # ── Section 1: Data Overview ──
    sections.append(r'% === Section: Data Overview and Pipeline Execution ===')
    sections.append('')
    sections.append(_gen_service_completion_table(data))
    sections.append('')
    sections.append(_gen_per_model_service_table(data))
    
    # ── Section 2: Code Volume ──
    sections.append('')
    sections.append(r'% === Section: Code Volume and Defect Density ===')
    sections.append('')
    sections.append(_gen_code_composition_table(data))
    sections.append('')
    sections.append(_gen_severity_table(data, note=_sev_note))
    
    # ── Section 3: Static Analysis (14 tools) ──
    sections.append('')
    sections.append(r'% === Section: Static Analysis Results ===')
    
    static_tool_info = {
        'bandit': ('Bandit: Python Security Linter Results by Model', 'tab:tool_bandit'),
        'semgrep': ('Semgrep: Pattern-Based Security Analysis Results by Model', 'tab:tool_semgrep'),
        'pylint': ('Pylint: Python Code Quality Results by Model', 'tab:tool_pylint'),
        'ruff': ('Ruff: Python Linting Results by Model', 'tab:tool_ruff'),
        'mypy': ('Mypy: Python Type Checking Results by Model', 'tab:tool_mypy'),
        'vulture': ('Vulture: Dead Code Detection Results by Model', 'tab:tool_vulture'),
        'radon': ('Radon: Python Complexity Analysis Results by Model', 'tab:tool_radon'),
        'safety': ('Safety: Python Dependency Vulnerability Results by Model', 'tab:tool_safety'),
        'pip-audit': ('Pip-audit: Python Package Audit Results by Model', 'tab:tool_pipaudit'),
        'detect-secrets': ('Detect-secrets: Secret Detection Results by Model', 'tab:tool_detectsecrets'),
        'eslint': ('ESLint: JavaScript Linting Results by Model', 'tab:tool_eslint'),
        'npm-audit': ('npm-audit: JavaScript Dependency Vulnerability Results by Model', 'tab:tool_npmaudit'),
        'stylelint': ('Stylelint: CSS Linting Results by Model', 'tab:tool_stylelint'),
        'html-validator': ('HTML-validator: Markup Validation Results by Model', 'tab:tool_htmlvalidator'),
    }
    
    for tn, (caption, label) in static_tool_info.items():
        td = data['static_tools'].get(tn)
        if td is None:
            sections.append(f'\n% Tool {tn} not found in data')
            continue
        sections.append('')
        sections.append(_gen_findings_tool_table(tn, td, loc_data, caption, label,
                                                  note=_static_tool_notes.get(tn, '')))
    
    # ── Section 4: Dynamic Analysis ──
    sections.append('')
    sections.append(r'% === Section: Dynamic Analysis Results ===')
    
    # ZAP — custom table with risk breakdown
    sections.append('')
    sections.append(_gen_zap_table(data, note=_deployed_note))
    
    # Nmap — diagnostic
    nmap_data = data['dynamic_tools'].get('nmap')
    if nmap_data:
        sections.append('')
        sections.append(_gen_diagnostic_tool_table(
            'nmap', nmap_data, data.get('dynamic_diagnostics', {}),
            'Nmap: Network Scanning Results by Model', 'tab:tool_nmap'))
    
    # Curl — findings-based
    curl_data = data['dynamic_tools'].get('curl')
    if curl_data:
        sections.append('')
        sections.append(_gen_findings_tool_table(
            'curl', curl_data, loc_data,
            'Curl: HTTP Probe Results by Model', 'tab:tool_curl'))
    
    # Curl endpoint tester — custom with pass/fail
    sections.append('')
    sections.append(_gen_curl_endpoint_table(data))
    
    # Connectivity — diagnostic
    conn_data = data['dynamic_tools'].get('connectivity')
    if conn_data:
        sections.append('')
        sections.append(_gen_diagnostic_tool_table(
            'connectivity', conn_data, data.get('dynamic_diagnostics', {}),
            'Connectivity: Network Verification Results by Model', 'tab:tool_connectivity'))
    
    # Port scan — diagnostic
    ps_data = data['dynamic_tools'].get('port-scan')
    if ps_data:
        sections.append('')
        sections.append(_gen_diagnostic_tool_table(
            'port-scan', ps_data, data.get('dynamic_diagnostics', {}),
            'Port Scan: Port Exposure Verification Results by Model', 'tab:tool_portscan'))
    
    # ── Section 5: Performance Testing ──
    sections.append('')
    sections.append(r'% === Section: Performance Testing Results ===')
    
    perf_tool_info = {
        'ab': ('Apache Bench: Load Testing Results by Model', 'tab:tool_ab'),
        'locust': ('Locust: Load Testing Results by Model', 'tab:tool_locust'),
        'artillery': ('Artillery: Load Testing Results by Model', 'tab:tool_artillery'),
        'aiohttp': ('aiohttp: Async HTTP Testing Results by Model', 'tab:tool_aiohttp'),
    }
    
    for tn, (caption, label) in perf_tool_info.items():
        td = data['performance_tools'].get(tn)
        if td is None:
            sections.append(f'\n% Tool {tn} not found in data')
            continue
        sections.append('')
        sections.append(_gen_perf_tool_table(tn, td, caption, label, note=_deployed_note))
    
    # ── Section 6: AI Analysis ──
    sections.append('')
    sections.append(r'% === Section: AI-Based Analysis Results ===')
    
    # Requirements scanner
    rs_data = data['ai_tools'].get('requirements-scanner')
    if rs_data:
        sections.append('')
        sections.append(_gen_ai_tool_table(
            'requirements-scanner', rs_data,
            'Requirements Scanner: Compliance Check Results by Model', 'tab:tool_reqscanner',
            note=_compliance_penalty_note))
    
    # Code quality analyzer
    cq_data = data['ai_tools'].get('code-quality-analyzer')
    if cq_data:
        sections.append('')
        sections.append(_gen_ai_tool_table(
            'code-quality-analyzer', cq_data,
            'Code Quality Analyzer: AI Review Results by Model', 'tab:tool_codequalanalyzer'))
    
    # AI compliance summary (backend/frontend/admin breakdown)
    sections.append('')
    sections.append(_gen_ai_compliance_summary(data, note=(
        'Overall scores include a 0.70 weighting for non-deployed apps; '
        'backend, frontend, and admin columns show unpenalised component scores.'
    )))
    
    # ── Section 7: Heatmap ──
    sections.append('')
    sections.append(r'% === Section: Tool Findings Heatmap ===')
    sections.append('')
    sections.append(_gen_heatmap_table(data))
    
    # ── Section 8: Rankings ──
    sections.append('')
    sections.append(r'% === Section: Operational Research Model Rankings ===')
    sections.append('')
    sections.append(_gen_topsis_table(data, note=_ranking_note))
    sections.append('')
    sections.append(_gen_wsm_table(data, note=_ranking_note))
    sections.append('')
    sections.append(_gen_correlation_table(data, note=_corr_note))
    
    # ── Section 9: Reproducibility ──
    sections.append('')
    sections.append(r'% === Section: Reproducibility ===')
    sections.append('')
    sections.append(_gen_reproducibility_tables(data))
    
    return '\n'.join(sections)


def main() -> None:
    parser = argparse.ArgumentParser(description='Generate LaTeX tables for thesis')
    parser.add_argument('-i', '--input', default='thesis_data.json',
                        help='Input thesis_data.json file')
    parser.add_argument('-o', '--output', default='reports/thesis_tables.tex',
                        help='Output LaTeX file')
    args = parser.parse_args()
    
    with open(args.input) as f:
        data = json.load(f)
    
    report = generate_report(data)
    
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w') as f:
        f.write(report)
    
    # Count tables generated
    table_count = report.count(r'\begin{table}')
    print(f'Generated {table_count} tables → {out_path}')


if __name__ == '__main__':
    main()
