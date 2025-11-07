"""Debug template catalog structure."""
import sys
import json
sys.path.insert(0, 'src')

from app.factory import create_app
from app.services.generation import get_generation_service

app = create_app()

with app.app_context():
    service = get_generation_service()
    templates = service.get_template_catalog()
    
    print(f"Total templates: {len(templates)}\n")
    
    # Get one template and show its structure
    todo = next((t for t in templates if t['slug'] == 'crud_todo_list'), None)
    
    if todo:
        print("crud_todo_list template structure:")
        print(json.dumps(todo, indent=2))
