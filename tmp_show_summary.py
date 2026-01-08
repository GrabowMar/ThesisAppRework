#!/usr/bin/env python3
"""Display analysis results summary."""
import json
import os
from pathlib import Path

results_dir = Path("/app/results/google_gemini-2.5-flash/app3/task_fae101a76e42")

# Find the JSON file
json_files = list(results_dir.glob("*.json"))
print(f"Found {len(json_files)} JSON files in {results_dir}")

for jf in json_files:
    print(f"  - {jf.name} ({jf.stat().st_size} bytes)")

# Load main result file (largest one, not manifest)
main_file = None
for jf in json_files:
    if "manifest" not in jf.name:
        main_file = jf
        break

if not main_file:
    print("ERROR: No main result file found")
    exit(1)

print(f"\nLoading: {main_file.name}")
with open(main_file) as f:
    data = json.load(f)

# Display structure
print("\n=== TOP LEVEL KEYS ===")
for key in data.keys():
    val = data[key]
    if isinstance(val, dict):
        print(f"  {key}: dict with {len(val)} keys")
    elif isinstance(val, list):
        print(f"  {key}: list with {len(val)} items")
    else:
        print(f"  {key}: {type(val).__name__}")

# Try to find summary
results = data.get("results", data)
summary = results.get("summary", {})

print("\n=== SUMMARY ===")
if summary:
    for k, v in summary.items():
        print(f"  {k}: {v}")
else:
    print("  No summary found, checking other locations...")
    if "summary" in data:
        print(f"  data.summary: {data['summary']}")

# Tools
tools = results.get("tools", {})
print(f"\n=== TOOLS ({len(tools)}) ===")
for tool_name, tool_data in tools.items():
    if isinstance(tool_data, dict):
        status = tool_data.get("status", "unknown")
        findings = tool_data.get("findings_count", tool_data.get("total_issues", "?"))
        print(f"  {tool_name}: status={status}, findings={findings}")
    else:
        print(f"  {tool_name}: {type(tool_data).__name__}")

# Services
services = results.get("services", {})
print(f"\n=== SERVICES ({len(services)}) ===")
for svc_name in services.keys():
    print(f"  - {svc_name}")

print("\n=== DONE ===")
