import re
from collections import Counter

with open('results_page.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Count 'Skipped' badges
skipped_badges = re.findall(r'badge[^>]*>Skipped</span>', html)
print(f'Found {len(skipped_badges)} "Skipped" badges')

# Get all status badges
all_badges = re.findall(r'badge[^>]*>(\s*\w+\s*)</span>', html)
status_badges = [b.strip().lower() for b in all_badges if b.strip().lower() in 
    ['success', 'error', 'failed', 'timeout', 'skipped', 'no_issues', 'completed']]

badge_counts = Counter(status_badges)

print()
print('Tool Status Distribution:')
for status, count in badge_counts.most_common():
    print(f'  {status:12} - {count} tools')
    
print()
print('Summary:')
total_tools = sum(badge_counts.values())
print(f'  Total tools with status: {total_tools}')
print(f'  Legitimate statuses: {total_tools - badge_counts.get("skipped", 0)}')
print(f'  Generic "Skipped": {badge_counts.get("skipped", 0)}')
