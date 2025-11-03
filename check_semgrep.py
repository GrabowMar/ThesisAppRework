import json
from pathlib import Path

result_file = Path("results/anthropic_claude-4.5-sonnet-20250929/app1/task_sarif_extraction_test_v2/anthropic_claude-4.5-sonnet-20250929_app1_task_sarif_extraction_test_v2_20251103_181056.json")

with open(result_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

semgrep = data['results']['services']['static']['analysis']['results']['python']['semgrep']

print("Semgrep keys:")
for key, value in semgrep.items():
    if isinstance(value, (list, dict)):
        size = len(json.dumps(value))
        print(f"  {key}: {type(value).__name__} with {size:,} bytes ({size/1024:.2f} KB)")
        if isinstance(value, list):
            print(f"    Length: {len(value)} items")
        elif isinstance(value, dict):
            print(f"    Keys: {len(value)} keys")
            if len(value) < 20:
                for k in value.keys():
                    print(f"      - {k}")
    else:
        print(f"  {key}: {value}")
