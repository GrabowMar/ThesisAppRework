import json
from pathlib import Path

result_file = Path("results/anthropic_claude-4.5-sonnet-20250929/app1/task_sarif_extraction_test_v2/anthropic_claude-4.5-sonnet-20250929_app1_task_sarif_extraction_test_v2_20251103_181056.json")

with open(result_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Check security service for semgrep
security = data['results']['services']['security']['analysis']

# Find semgrep in security service results
print("Security service tool_results:")
if 'tool_results' in security:
    for tool_name, tool_data in security['tool_results'].items():
        print(f"  {tool_name}")
        if isinstance(tool_data, dict) and 'sarif' in tool_data:
            sarif = tool_data['sarif']
            if isinstance(sarif, dict):
                if 'sarif_file' in sarif:
                    print(f"    -> SARIF reference: {sarif['sarif_file']}")
                else:
                    # Still has embedded SARIF!
                    size = len(json.dumps(sarif))
                    print(f"    -> EMBEDDED SARIF! {size:,} bytes ({size/1024:.2f} KB)")
            else:
                size = len(json.dumps(sarif))
                print(f"    -> SARIF object: {size:,} bytes ({size/1024:.2f} KB)")

# Also check results structure if it exists
if 'results' in security:
    print("\nSecurity service results structure:")
    for category, tools in security['results'].items():
        print(f" {category}:")
        if isinstance(tools, dict):
            for tool_name, tool_data in tools.items():
                print(f"    {tool_name}")
                if isinstance(tool_data, dict) and 'sarif' in tool_data:
                    sarif = tool_data['sarif']
                    if isinstance(sarif, dict):
                        if 'sarif_file' in sarif:
                            print(f"      -> SARIF reference: {sarif['sarif_file']}")
                        else:
                            size = len(json.dumps(sarif))
                            print(f"      -> EMBEDDED SARIF! {size:,} bytes ({size/1024:.2f} KB)")
