import json

# Check main result file
main_file = 'results/anthropic_claude-4.5-sonnet-20250929/app10/task_765a3b62087f/anthropic_claude-4.5-sonnet-20250929_app10_task_765a3b62087f.json'
data = json.load(open(main_file))

print('='*60)
print('MAIN RESULT FILE')
print('='*60)
print(f'Total findings in metadata: {data.get("metadata", {}).get("total_findings")}')
print(f'Services: {list(data.get("services", {}).keys())}')

for service_name, service_data in data.get('services', {}).items():
    print(f'\n{service_name}:')
    print(f'  Status: {service_data.get("status")}')
    print(f'  Findings: {len(service_data.get("findings", []))}')
    print(f'  Issue count: {service_data.get("issue_count")}')
    print(f'  Total issues: {service_data.get("total_issues")}')
    
    # Check for tools section
    if 'tools' in service_data:
        print(f'  Tools: {list(service_data["tools"].keys())}')
        for tool_name, tool_data in service_data['tools'].items():
            issues = len(tool_data.get('findings', [])) if isinstance(tool_data.get('findings'), list) else tool_data.get('issue_count', 0)
            print(f'    {tool_name}: {issues} issues')