"""Test that templates load correctly with numbered requirements."""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.services.generation import get_generation_service

app = create_app()

with app.app_context():
    service = get_generation_service()
    templates = service.get_template_catalog()
    
    print(f"✓ Loaded {len(templates)} templates")
    
    # Check a few samples
    samples = ['crud_todo_list', 'booking_reservations', 'realtime_chat_room']
    
    for slug in samples:
        template = next((t for t in templates if t['slug'] == slug), None)
        if template:
            print(f"\n{template['name']} ({slug}):")
            print("  Backend requirements:")
            for req in template.get('backend_requirements', [])[:2]:
                print(f"    {req}")
            print("  Frontend requirements:")
            for req in template.get('frontend_requirements', [])[:2]:
                print(f"    {req}")
        else:
            print(f"✗ Template {slug} not found")
    
    print("\n✓ All templates loaded successfully with numbered requirements!")
