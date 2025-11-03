import json
from pathlib import Path

result_file = Path("results/anthropic_claude-4.5-sonnet-20250929/app1/task_sarif_extraction_test_v2/anthropic_claude-4.5-sonnet-20250929_app1_task_sarif_extraction_test_v2_20251103_181056.json")

with open(result_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

services = data['results']['services']

print("Service sizes:")
for service_name, service_data in services.items():
    size = len(json.dumps(service_data))
    print(f"  {service_name}: {size:,} bytes ({size/1024/1024:.2f} MB)")

# Drill into static
if 'static' in services:
    static = services['static']['analysis']
    results = static.get('results', {})
    print("\nStatic analysis categories:")
    for category, cat_data in results.items():
        size = len(json.dumps(cat_data))
        print(f"  {category}: {size:,} bytes ({size/1024:.2f} KB)")
        
        if isinstance(cat_data, dict):
            print(f"    Tools in {category}:")
            for tool, tool_data in cat_data.items():
                size = len(json.dumps(tool_data))
                print(f"      {tool}: {size:,} bytes ({size/1024:.2f} KB)")
                
                # Check for large arrays
                if isinstance(tool_data, dict):
                    for key, value in tool_data.items():
                        if isinstance(value, (list, dict)):
                            val_size = len(json.dumps(value))
                            if val_size > 10000:  # >10KB
                                print(f"        .{key}: {val_size:,} bytes ({val_size/1024:.2f} KB)")
