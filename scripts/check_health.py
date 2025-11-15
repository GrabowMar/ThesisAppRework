"""Quick health check."""
import requests

try:
    r = requests.get("http://127.0.0.1:5000/health", timeout=2)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text}")
except Exception as e:
    print(f"Error: {e}")
