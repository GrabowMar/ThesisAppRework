import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app.services.docker_manager import DockerManager
m=DockerManager()
print('project_root', m.project_root)
print('models_dir', m.models_dir)
path=m._get_compose_path('nousresearch_hermes-4-405b',1)
print('compose_path', path)
print('exists', path.exists())
import json
print(json.dumps(m.debug_compose_resolution('nousresearch_hermes-4-405b',1), indent=2))
