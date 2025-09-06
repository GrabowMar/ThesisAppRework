import sys
import json
from pathlib import Path

sys.path.insert(0, 'src')

file_path = Path('src/misc/model_capabilities.json')
print(f'File exists: {file_path.exists()}')

with open(file_path, 'r') as f:
    data = json.load(f)

print(f'Keys: {list(data.keys())}')
print(f'Model count: {len(data.get("models", {}))}')

# Now try to call the populate method
from app.factory import create_app
from app.services.model_service import ModelService

app = create_app()
with app.app_context():
    model_service = ModelService(app)
    result = model_service._populate_model_capabilities(file_path)
    print(f'Population result: {result}')