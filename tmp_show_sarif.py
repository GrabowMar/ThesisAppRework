#!/usr/bin/env python3
"""Check SARIF data for actual findings."""
import json
from pathlib import Path

results_dir = Path("/app/results/google_gemini-2.5-flash/app3/task_fae101a76e42")
json_files = list(results_dir.glob("*.json"))

if json_files:
    main_file = max(json_files, key=lambda x: x.stat().st_size)
    print(f"Reading: {main_file.name}")
    
    with open(main_file) as f:
        data = json.load(f)
    
    payload = data.get('services', {}).get('static-analyzer', {}).get('payload', {})
    results = payload.get('results', {})
    
    # Check bandit SARIF
    bandit = results.get('python', {}).get('bandit', {})
    print(f"\n=== BANDIT ===")
    print(f"issue_count: {bandit.get('issue_count')}")
    print(f"total_issues: {bandit.get('total_issues')}")
    sarif = bandit.get('sarif', {})
    if isinstance(sarif, dict):
        runs = sarif.get('runs', [])
        if runs:
            results_in_sarif = runs[0].get('results', [])
            print(f"SARIF results: {len(results_in_sarif)} items")
            if results_in_sarif:
                r = results_in_sarif[0]
                print(f"Sample finding:")
                print(f"  ruleId: {r.get('ruleId')}")
                print(f"  level: {r.get('level')}")
                msg = r.get('message', {})
                print(f"  message: {msg.get('text', '')[:200]}...")
                locs = r.get('locations', [])
                if locs:
                    loc = locs[0].get('physicalLocation', {})
                    print(f"  file: {loc.get('artifactLocation', {}).get('uri')}")
                    region = loc.get('region', {})
                    print(f"  line: {region.get('startLine')}")
    
    # Check semgrep SARIF
    semgrep = results.get('python', {}).get('semgrep', {})
    print(f"\n=== SEMGREP ===")
    print(f"issue_count: {semgrep.get('issue_count')}")
    print(f"total_issues: {semgrep.get('total_issues')}")
    sarif = semgrep.get('sarif', {})
    if isinstance(sarif, dict):
        runs = sarif.get('runs', [])
        if runs:
            results_in_sarif = runs[0].get('results', [])
            print(f"SARIF results: {len(results_in_sarif)} items")
            for i, r in enumerate(results_in_sarif[:3]):  # Show up to 3
                print(f"\n  Finding #{i+1}:")
                print(f"    ruleId: {r.get('ruleId')}")
                print(f"    level: {r.get('level')}")
                msg = r.get('message', {})
                print(f"    message: {msg.get('text', '')[:150]}...")
                locs = r.get('locations', [])
                if locs:
                    loc = locs[0].get('physicalLocation', {})
                    print(f"    file: {loc.get('artifactLocation', {}).get('uri')}")
                    region = loc.get('region', {})
                    print(f"    line: {region.get('startLine')}")
    
    # Check eslint SARIF
    eslint = results.get('javascript', {}).get('eslint', {})
    print(f"\n=== ESLINT ===")
    print(f"issue_count: {eslint.get('issue_count')}")
    print(f"total_issues: {eslint.get('total_issues')}")
    sarif = eslint.get('sarif', {})
    if isinstance(sarif, dict):
        runs = sarif.get('runs', [])
        if runs:
            results_in_sarif = runs[0].get('results', [])
            print(f"SARIF results: {len(results_in_sarif)} items")
            for i, r in enumerate(results_in_sarif[:3]):  # Show up to 3
                print(f"\n  Finding #{i+1}:")
                print(f"    ruleId: {r.get('ruleId')}")
                print(f"    level: {r.get('level')}")
                msg = r.get('message', {})
                print(f"    message: {msg.get('text', '')[:150]}...")
                locs = r.get('locations', [])
                if locs:
                    loc = locs[0].get('physicalLocation', {})
                    print(f"    file: {loc.get('artifactLocation', {}).get('uri')}")
                    region = loc.get('region', {})
                    print(f"    line: {region.get('startLine')}")

else:
    print("No JSON files found")
