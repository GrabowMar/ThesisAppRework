#!/bin/bash
API_URL="https://localhost/api/automation/pipelines"
TOKEN="r6QP17pZSQ3o-M1bQ64z9tLcHnaVfh_ITMIVB0LFYCf3Y96FS2CjmcvpnJUWHrur"

curl -sL "$API_URL" -k -H "Authorization: Bearer $TOKEN" | python3 -c "
import sys, json
resp = json.load(sys.stdin)
data = resp.get('data', [])
if isinstance(data, dict):
    data = [data]
running = [p for p in data if p and p.get('status') == 'running']
completed = [p for p in data if p and p.get('status') == 'completed']
print(f'=== Pipeline Status ===')
print(f'Running: {len(running)} | Completed: {len(completed)}')
print()
for p in running[:5]:
    progress = p.get('progress') or {}
    gen = progress.get('generation') or {}
    ana = progress.get('analysis') or {}
    print(f'{p.get(\"id\")} | {p.get(\"stage\")}')
    print(f'  Gen: {gen.get(\"completed\",0)}/{gen.get(\"total\",0)} | Ana: {ana.get(\"completed\",0)}/{ana.get(\"total\",0)}')
"
