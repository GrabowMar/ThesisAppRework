#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app.factory import create_app
from app.models import GeneratedApplication

app = create_app()

with app.app_context():
    apps = GeneratedApplication.query.all()
    print(f"Found {len(apps)} applications in database:")
    for app_obj in apps[:20]:
        print(f"  - {app_obj.model_slug}/app{app_obj.app_number} (ID: {app_obj.id})")
