import json
import sys

# Load the latest result - update with new task ID
result_file = "results/openai_gpt-4.1-2025-04-14/app3/task_analysis_20251031_184920/openai_gpt-4.1-2025-04-14_app3_task_analysis_20251031_184920_20251031_184920.json"

with open(result_file) as f:
    result = json.load(f)

# Check for SARIF tools
print("=== SARIF Tool Status ===")
sarif_tools = ['bandit', 'pylint', 'semgrep', 'mypy', 'eslint', 'ruff']
tools = result.get('results', {}).get('tools', {})

for tool_name in sarif_tools:
    tool_data = tools.get(tool_name, {})
    status = tool_data.get('status', 'missing')
    total_issues = tool_data.get('total_issues', 0)
    executed = tool_data.get('executed', False)
    print(f"  {tool_name}: {status} (executed: {executed}, issues: {total_issues})")

print(f"\n=== Overall Statistics ===")
print(f"Total tools executed: {len(tools)}")
print(f"Total findings aggregated: {len(result.get('results', {}).get('findings', []))}")

# List all tools
print(f"\n=== All Tools ===")
for tool_name, tool_data in sorted(tools.items()):
    status = tool_data.get('status', 'unknown')
    issues = tool_data.get('total_issues', 0)
    executed = tool_data.get('executed', False)
    emoji = "✅" if status == "success" else "❌" if status == "error" else "⚠️"
    print(f"{emoji} {tool_name}: {status} (executed: {executed}, issues: {issues})")
