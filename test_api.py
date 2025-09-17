import requests
import json

response = requests.get('http://127.0.0.1:5000/api/dashboard/tool-registry-summary')
print('Status:', response.status_code)
if response.status_code == 200:
    data = response.json()
    for tool in data.get('tools', [])[:3]:
        print(f'Tool: {tool.get("name")} - Available: {tool.get("available")} - Source: {tool.get("availability_source")}')
else:
    print('Response:', response.text)
