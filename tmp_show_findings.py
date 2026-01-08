#!/usr/bin/env python3
"""Show sample findings from each tool."""
import json
from pathlib import Path

results_dir = Path("/app/results/google_gemini-2.5-flash/app3/task_fae101a76e42")
main_file = results_dir / "google_gemini-2.5-flash_app3_task_fae101a76e42_20260107_215621.json"

with open(main_file) as f:
    data = json.load(f)

services = data.get("services", {})
static = services.get("static-analyzer", {})
payload = static.get("payload", {})
results = payload.get("results", {})

print("=" * 60)
print("SAMPLE FINDINGS FROM EACH TOOL")
print("=" * 60)

# Bandit findings
python_results = results.get("python", {})
bandit = python_results.get("bandit", {})
if isinstance(bandit, dict):
    issues = bandit.get("issues", [])
    print(f"\n=== BANDIT ({len(issues)} issues) ===")
    for issue in issues[:3]:
        if isinstance(issue, dict):
            print(f"  - {issue.get('severity', '?')}: {issue.get('test_id', '?')} - {str(issue.get('issue_text', ''))[:80]}")
            print(f"    File: {issue.get('filename', '?')}:{issue.get('line_number', '?')}")

# Semgrep findings
semgrep = python_results.get("semgrep", {})
if isinstance(semgrep, dict):
    issues = semgrep.get("issues", semgrep.get("results", []))
    print(f"\n=== SEMGREP ({len(issues) if isinstance(issues, list) else '?'} issues) ===")
    if isinstance(issues, list):
        for issue in issues[:3]:
            if isinstance(issue, dict):
                check_id = issue.get("check_id", issue.get("rule_id", "?"))
                msg = issue.get("extra", {}).get("message", "") if isinstance(issue.get("extra"), dict) else ""
                print(f"  - {check_id}")
                if msg:
                    print(f"    {msg[:80]}")

# ESLint findings  
js_results = results.get("javascript", {})
eslint = js_results.get("eslint", {})
if isinstance(eslint, dict):
    issues = eslint.get("issues", [])
    print(f"\n=== ESLINT ({len(issues)} issues) ===")
    for issue in issues[:5]:
        if isinstance(issue, dict):
            rule = issue.get("ruleId", "?")
            msg = issue.get("message", "")[:60]
            severity = "error" if issue.get("severity") == 2 else "warning"
            print(f"  - [{severity}] {rule}: {msg}")
            print(f"    File: {issue.get('filePath', '?')}:{issue.get('line', '?')}")

print("\n" + "=" * 60)
print("Analysis complete!")
