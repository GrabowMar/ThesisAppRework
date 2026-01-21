import json

# Check service JSON
data = json.load(open('results/anthropic_claude-4.5-sonnet-20250929/app10/task_765a3b62087f/services/static-analyzer.json'))

results = data.get('analysis', {}).get('results', {})
total_issues = 0

for lang, tools in results.items():
    if isinstance(tools, dict):
        print(f"\n{lang}:")
        for tool_name, tool_data in tools.items():
            if isinstance(tool_data, dict):
                issues = len(tool_data.get('issues', []))
                total_issues += issues
                print(f"  {tool_name}: {issues} issues")

print(f"\nTotal issues in service JSON: {total_issues}")

# Check main result file
main_data = json.load(open('results/anthropic_claude-4.5-sonnet-20250929/app10/task_765a3b62087f/anthropic_claude-4.5-sonnet-20250929_app10_task_765a3b62087f.json'))
print(f"Total in main file metadata: {main_data.get('metadata', {}).get('total_findings')}")
print(f"Total in main file summary: {main_data.get('summary', {}).get('total_findings')}")
