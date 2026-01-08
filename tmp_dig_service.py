#!/usr/bin/env python3
"""Dig into service details."""
import json
from pathlib import Path

results_dir = Path("/app/results/google_gemini-2.5-flash/app3/task_fae101a76e42")
main_file = results_dir / "google_gemini-2.5-flash_app3_task_fae101a76e42_20260107_215621.json"

with open(main_file) as f:
    data = json.load(f)

services = data.get("services", {})
static = services.get("static-analyzer", {})

print("=== STATIC-ANALYZER SERVICE ===")
print(f"Keys: {list(static.keys())}")

for key, val in static.items():
    if isinstance(val, dict):
        print(f"\n{key} (dict with {len(val)} keys):")
        for k2, v2 in list(val.items())[:10]:
            if isinstance(v2, (dict, list)):
                print(f"    {k2}: {type(v2).__name__} ({len(v2)} items)")
            else:
                val_str = str(v2)[:100]
                print(f"    {k2}: {val_str}")
    elif isinstance(val, list):
        print(f"\n{key} (list with {len(val)} items)")
        for item in val[:3]:
            print(f"    - {str(item)[:100]}")
    else:
        print(f"\n{key}: {str(val)[:200]}")

# Check analysis sub-structure
analysis = static.get("analysis", {})
if analysis:
    print("\n=== ANALYSIS SUBSTRUCTURE ===")
    for key in analysis.keys():
        val = analysis[key]
        if isinstance(val, dict):
            print(f"  {key}: dict with {len(val)} keys - {list(val.keys())[:5]}")
        elif isinstance(val, list):
            print(f"  {key}: list with {len(val)} items")
        else:
            print(f"  {key}: {str(val)[:100]}")
