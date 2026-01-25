
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path.cwd() / 'src'))
sys.path.insert(0, str(Path.cwd() / 'analyzer'))

from analyzer.analyzer_manager import AnalyzerManager

manager = AnalyzerManager()
print(f"Is running in docker: {manager._is_running_in_docker()}")

# specific model and app from logs
model_slug = "anthropic/claude-3-5-haiku"
app_number = 5

print(f"Resolving ports for {model_slug} app {app_number}...")
ports = manager._resolve_app_ports(model_slug, app_number)
print(f"Ports: {ports}")

if ports:
    backend_port, frontend_port = ports
    # Mimic tasks.py logic
    safe_slug = model_slug.replace('/', '-') # tasks.py said replace _ with - but slug has / which usually becomes - or _
    # tasks.py said: safe_slug = model_slug.replace('_', '-')
    # But model_slug is anthropic/claude...
    
    # tasks.py line 462: safe_slug = model_slug.replace('_', '-')
    # Warning: tasks.py might be assuming model_slug has underscores instead of slashes?
    
    # Let's check how docker compose names them.
    # Usually it's projectname-servicename-1
    # Services in generated docker-compose?
    pass
