#!/usr/bin/env python3
import sys
sys.path.insert(0, 'src')

from app import create_app
from core_services import get_container_names

app = create_app()

with app.app_context():
    try:
        backend_name, frontend_name = get_container_names('anthropic_claude-3.7-sonnet', 1)
        print(f'Expected backend name: {backend_name}')
        print(f'Expected frontend name: {frontend_name}')
        
        # Also check app4 which we can see is running
        backend_name4, frontend_name4 = get_container_names('anthropic_claude-3.7-sonnet', 4)
        print(f'Expected backend name (app4): {backend_name4}')
        print(f'Expected frontend name (app4): {frontend_name4}')
        
    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()
