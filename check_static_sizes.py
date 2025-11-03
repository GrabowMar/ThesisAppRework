import json
from pathlib import Path

result_file = Path("results/anthropic_claude-4.5-sonnet-20250929/app1/task_sarif_extraction_test_v2/anthropic_claude-4.5-sonnet-20250929_app1_task_sarif_extraction_test_v2_20251103_181056.json")

with open(result_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Check static service for what's large
static = data['results']['services']['static']['analysis']

# Check tool_results
if 'tool_results' in static:
    print("Static service tool_results:")
    for tool_name, tool_data in static['tool_results'].items():
        size = len(json.dumps(tool_data))
        print(f"  {tool_name}: {size:,} bytes ({size/1024:.2f} KB)")
        
        if isinstance(tool_data, dict):
            for key, value in tool_data.items():
                if isinstance(value, (list, dict)):
                    val_size = len(json.dumps(value))
                    if val_size > 10000:  # >10KB
                        print(f"    .{key}: {val_size:,} bytes ({val_size/1024:.2f} KB)")

# Check results structure 
if 'results' in static:
    print("\nStatic service results/python:")
    python_tools = static['results']['python']
    for tool_name, tool_data in python_tools.items():
        size = len(json.dumps(tool_data))
        print(f"  {tool_name}: {size:,} bytes ({size/1024:.2f} KB)")
        
        if isinstance(tool_data, dict):
            for key, value in tool_data.items():
                if key == 'sarif':
                    if isinstance(value, dict) and 'sarif_file' in value:
                        print(f"    .sarif -> {value['sarif_file']}")
                    else:
                        val_size = len(json.dumps(value))
                        print(f"    .sarif: EMBEDDED! {val_size:,} bytes ({val_size/1024:.2f} KB)")
                elif isinstance(value, (list, dict)):
                    val_size = len(json.dumps(value))
                    if val_size > 10000:  # >10KB
                        print(f"    .{key}: {val_size:,} bytes ({val_size/1024:.2f} KB)")
