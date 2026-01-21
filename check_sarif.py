import json

# Check SARIF files
bandit_file = 'results/anthropic_claude-4.5-sonnet-20250929/app10/task_765a3b62087f/sarif/static-analyzer_python_bandit.sarif.json'
data = json.load(open(bandit_file))

runs = data.get('runs', [])
if runs:
    results = runs[0].get('results', [])
    print(f'Bandit SARIF results: {len(results)}')
    
    # Show first few results
    for i, result in enumerate(results[:3]):
        print(f'\nResult {i+1}:')
        print(f'  ruleId: {result.get("ruleId")}')
        print(f'  level: {result.get("level")}')
        message = result.get('message', {})
        print(f'  message: {message.get("text", "")[:80]}')
else:
    print('No runs found in SARIF')