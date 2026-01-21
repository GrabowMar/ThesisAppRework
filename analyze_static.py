import json

data = json.load(open('results/anthropic_claude-4.5-sonnet-20250929/app10/task_765a3b62087f/services/static-analyzer.json'))
print(f'issue_count: {data.get("issue_count")}')
print(f'total_issues: {data.get("total_issues")}')
print(f'findings: {len(data.get("findings", []))}')
print(f'results keys: {list(data.get("results", {}).keys())}')

results = data.get('results', {})
for lang, lang_tools in results.items():
    if isinstance(lang_tools, dict):
        print(f'\nLanguage: {lang}')
        for tool, tool_data in lang_tools.items():
            if isinstance(tool_data, dict):
                print(f'  {tool}: total_issues={tool_data.get("total_issues")}, issues={len(tool_data.get("issues", []))}')