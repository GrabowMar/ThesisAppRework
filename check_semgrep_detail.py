import json
from pathlib import Path

result_file = Path("results/anthropic_claude-4.5-sonnet-20250929/app1/task_sarif_extraction_test_v2/anthropic_claude-4.5-sonnet-20250929_app1_task_sarif_extraction_test_v2_20251103_181056.json")

with open(result_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

semgrep = data['results']['services']['static']['analysis']['results']['python']['semgrep']

print("Semgrep tool data keys:")
for key, value in semgrep.items():
    if isinstance(value, (list, dict)):
        size = len(json.dumps(value))
        print(f"  {key}: {type(value).__name__}, {size:,} bytes ({size/1024:.2f} KB)")
        if isinstance(value, list):
            print(f"    -> List with {len(value)} items")
            if len(value) > 0 and isinstance(value[0], dict):
                first_item_size = len(json.dumps(value[0]))
                print(f"    -> First item: {first_item_size} bytes")
                print(f"    -> First item keys: {list(value[0].keys())}")
    else:
        print(f"  {key}: {value}")
