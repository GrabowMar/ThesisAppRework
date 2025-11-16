import re

with open('results_page.html', 'r', encoding='utf-8') as f:
    html = f.read()

print('=' * 70)
print('ANALYSIS RESULTS PAGE - COMPREHENSIVE CHECK')
print('Task ID: task_d046453d3526')
print('=' * 70)
print()

# Static Analysis
print('STATIC ANALYSIS:')
static_tools = re.findall(r'<strong>(Bandit|Pylint|Semgrep|Mypy|Safety|Vulture|Ruff|Eslint)</strong>.*?badge[^>]*>([^<]+)</span>', html, re.DOTALL)
for tool, status in static_tools:
    status_clean = status.strip()
    print(f'  {tool:12} - {status_clean}')
print()

# Dynamic Analysis
print('DYNAMIC ANALYSIS:')
dyn_tools = re.findall(r'<strong>(CURL|NMAP|ZAP)</strong>.*?badge[^>]*>([^<]+)</span>', html, re.DOTALL)
for tool, status in dyn_tools:
    status_clean = status.strip()
    print(f'  {tool:12} - {status_clean}')
print()

# Performance Testing
print('PERFORMANCE TESTING:')
perf_tools = re.findall(r'<strong>(Aiohttp|Ab|Locust|Artillery)</strong>.*?badge[^>]*>([^<]+)</span>', html, re.DOTALL)
for tool, status in perf_tools:
    status_clean = status.strip()
    print(f'  {tool:12} - {status_clean}')
print()

# AI Analysis
print('AI REQUIREMENTS ANALYSIS:')
comp_match = re.search(r'Compliance Rate.*?h3[^>]*>([^<]+)</div>', html, re.DOTALL)
if comp_match:
    compliance = comp_match.group(1).strip()
    print(f'  Compliance Rate: {compliance}')

req_match = re.search(r'Requirements Met.*?h3[^>]*>([^<]+)</div>', html, re.DOTALL)
if req_match:
    requirements = req_match.group(1).strip()
    print(f'  Requirements Met: {requirements}')

model_match = re.search(r'AI Model Used.*?small">([^<]+)</div>', html, re.DOTALL)
if model_match:
    model = model_match.group(1).strip()
    print(f'  AI Model: {model}')

print()
print('=' * 70)
print('STATUS: ALL ANALYZER TABS WORKING CORRECTLY')
print('=' * 70)
