import json
import os
import glob
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATHS = [
    os.path.join(BASE, 'results'),
    os.path.join(BASE, 'analyzer', 'results'),
]


def load_json(path: str):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        return {'_error': str(e)}


def summarize_one(path: str) -> dict:
    data = load_json(path)
    rel = os.path.relpath(path, BASE)
    mtime = datetime.fromtimestamp(os.path.getmtime(path)).isoformat(sep=' ', timespec='seconds')

    # Expected schema:
    # {
    #   "metadata": { "analysis_type": "security" },
    #   "results": { "type": "...", "service": "...", "analysis": { "tools_used": [...], "results": { ... }, "summary": { "total_issues_found": N }}}
    # }
    meta = data.get('metadata', {}) if isinstance(data, dict) else {}
    top_results = data.get('results') if isinstance(data, dict) else {}
    if not isinstance(top_results, dict):
        top_results = {}
    analysis = top_results.get('analysis') if isinstance(top_results, dict) else {}
    if not isinstance(analysis, dict):
        analysis = {}

    # Prefer high-level analysis_type from metadata; fall back to results.type
    analysis_type = meta.get('analysis_type') or (top_results.get('type') if isinstance(top_results, dict) else None)

    # Tools used list lives under results.analysis.tools_used
    tools_used = analysis.get('tools_used')
    if isinstance(tools_used, dict):
        tools_used = list(tools_used.keys())

    # Nested tool keys: iterate results.analysis.results by language -> tool name
    nested_tools = set()
    analysis_results = analysis.get('results', {})
    if isinstance(analysis_results, dict):
        for lang_section, sub in analysis_results.items():
            # language section can be a dict with tool keys (e.g., 'python': {'bandit': {...}})
            if isinstance(sub, dict):
                for tname, tval in sub.items():
                    # Only record plausible tool entries
                    if isinstance(tname, str) and isinstance(tval, (dict, list)):
                        # Exclude generic keys that aren't tools
                        if tname not in {"status", "message", "file_counts", "security_files", "total_files"}:
                            nested_tools.add(tname)

    # Total issues: present in results.analysis.summary.total_issues_found (for static)
    total_issues = None
    summary = analysis.get('summary', {}) if isinstance(analysis, dict) else {}
    if isinstance(summary, dict):
        total_issues = summary.get('total_issues_found') or summary.get('total_issues')

    return {
        'file': rel,
        'modified': mtime,
        'analysis_type': analysis_type,
        'tools_used': tools_used,
        'nested_tools': sorted(nested_tools) if nested_tools else None,
        'total_issues': total_issues,
        'error': data.get('_error') if isinstance(data, dict) else None,
    }


def main():
    files = []
    for p in PATHS:
        if os.path.isdir(p):
            files.extend(glob.glob(os.path.join(p, '*.json')))
    files.sort(key=lambda f: os.path.getmtime(f), reverse=True)

    print(f"Found {len(files)} result files. Showing up to 50 most recent\n")
    rows = [summarize_one(f) for f in files[:50]]

    # Print compact report
    for r in rows:
        print(f"- {r['file']} | {r['modified']}\n  type={r['analysis_type']}  tools_used={r['tools_used']}  nested={r['nested_tools']}  total_issues={r['total_issues']}")

    # Aggregate quick counts per tool (if tools_used is list)
    tool_counts = {}
    for r in rows:
        tu = r.get('tools_used')
        if isinstance(tu, list):
            for t in tu:
                tool_counts[t] = tool_counts.get(t, 0) + 1
    if tool_counts:
        print("\nTool usage across recent files:")
        for t, c in sorted(tool_counts.items(), key=lambda x: (-x[1], x[0])):
            print(f"  {t}: {c}")


if __name__ == '__main__':
    main()
