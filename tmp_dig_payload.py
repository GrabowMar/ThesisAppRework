#!/usr/bin/env python3
"""Dig into payload details."""
import json
from pathlib import Path

results_dir = Path("/app/results/google_gemini-2.5-flash/app3/task_fae101a76e42")
main_file = results_dir / "google_gemini-2.5-flash_app3_task_fae101a76e42_20260107_215621.json"

with open(main_file) as f:
    data = json.load(f)

services = data.get("services", {})
static = services.get("static-analyzer", {})
payload = static.get("payload", {})

print("=== STATIC-ANALYZER PAYLOAD ===")
print(f"Tools used: {payload.get('tools_used')}")
print(f"Configuration applied: {payload.get('configuration_applied')}")
print(f"Analysis time: {payload.get('analysis_time')}")

summary = payload.get("summary", {})
print("\n=== SUMMARY ===")
for k, v in summary.items():
    print(f"  {k}: {v}")

results = payload.get("results", {})
print(f"\n=== RESULTS (keys: {list(results.keys())}) ===")

for lang, lang_results in results.items():
    print(f"\n--- {lang.upper()} ---")
    if isinstance(lang_results, dict):
        for tool, tool_data in lang_results.items():
            if isinstance(tool_data, dict):
                status = tool_data.get("status", "?")
                total = tool_data.get("total_issues", tool_data.get("total_issues_found", "?"))
                print(f"  {tool}: status={status}, issues={total}")
            else:
                print(f"  {tool}: {type(tool_data).__name__}")

# SARIF info
sarif = payload.get("sarif_export", {})
print(f"\n=== SARIF EXPORT ===")
print(f"  Keys: {list(sarif.keys())}")
if sarif.get("tools_with_sarif"):
    print(f"  Tools with SARIF: {sarif.get('tools_with_sarif')}")
if sarif.get("export_path"):
    print(f"  Export path: {sarif.get('export_path')}")
