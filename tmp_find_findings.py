#!/usr/bin/env python3
"""Find where findings are actually stored in the results JSON."""
import json
from pathlib import Path

results_dir = Path("/app/results/google_gemini-2.5-flash/app3/task_fae101a76e42")
json_files = list(results_dir.glob("*.json"))

if json_files:
    main_file = max(json_files, key=lambda x: x.stat().st_size)
    print(f"Reading: {main_file.name}")
    
    with open(main_file) as f:
        data = json.load(f)
    
    # Get the static analyzer payload
    payload = data.get('services', {}).get('static-analyzer', {}).get('payload', {})
    results = payload.get('results', {})
    
    # Check Python section
    python = results.get('python', {})
    print(f"\n=== PYTHON SECTION ===")
    for tool_name, tool_data in python.items():
        print(f"\n{tool_name.upper()}:")
        print(f"  Keys: {list(tool_data.keys())}")
        
        # Look for issues in various places
        if 'issues' in tool_data:
            issues = tool_data['issues']
            print(f"  issues: {len(issues)} items")
            if issues and len(issues) > 0:
                print(f"  Sample issue keys: {list(issues[0].keys()) if isinstance(issues[0], dict) else type(issues[0])}")
                # Show first issue
                issue = issues[0]
                print(f"  First issue: {json.dumps(issue, indent=4)[:500]}...")
        
        if 'results' in tool_data:
            inner_results = tool_data['results']
            print(f"  results: {type(inner_results).__name__}")
            if isinstance(inner_results, list):
                print(f"    Length: {len(inner_results)}")
                if inner_results:
                    print(f"    Sample: {json.dumps(inner_results[0], indent=4)[:500]}...")
            elif isinstance(inner_results, dict):
                print(f"    Keys: {list(inner_results.keys())}")
    
    # Check JavaScript section
    js = results.get('javascript', {})
    print(f"\n=== JAVASCRIPT SECTION ===")
    for tool_name, tool_data in js.items():
        print(f"\n{tool_name.upper()}:")
        print(f"  Keys: {list(tool_data.keys())}")
        
        if 'issues' in tool_data:
            issues = tool_data['issues']
            print(f"  issues: {len(issues)} items")
            if issues and len(issues) > 0:
                print(f"  Sample issue keys: {list(issues[0].keys()) if isinstance(issues[0], dict) else type(issues[0])}")
                issue = issues[0]
                print(f"  First issue: {json.dumps(issue, indent=4)[:500]}...")
        
        if 'results' in tool_data:
            inner_results = tool_data['results']
            print(f"  results: {type(inner_results).__name__}")
            if isinstance(inner_results, list):
                print(f"    Length: {len(inner_results)}")
                if inner_results:
                    print(f"    Sample: {json.dumps(inner_results[0], indent=4)[:500]}...")
            elif isinstance(inner_results, dict):
                print(f"    Keys: {list(inner_results.keys())}")
else:
    print("No JSON files found")
