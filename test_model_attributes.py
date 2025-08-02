#!/usr/bin/env python3
"""
Direct test of ModelCapability attributes
"""

import sys
sys.path.append('src')
from app import create_app
from models import ModelCapability

# Test direct attribute access
app = create_app()
with app.app_context():
    models = ModelCapability.query.all()
    print(f'Total models: {len(models)}')
    
    if models:
        m = models[0]
        print(f'Model object: {m}')
        print(f'Dir of model: {[attr for attr in dir(m) if not attr.startswith("_")]}')
        print()
        print(f'canonical_slug value: "{getattr(m, "canonical_slug", "MISSING")}"')
        print(f'model_name value: "{getattr(m, "model_name", "MISSING")}"')
        print(f'provider value: "{getattr(m, "provider", "MISSING")}"')
        
        # Test HTML template format
        print()
        print('Testing HTML template format:')
        print(f'<option value="{m.canonical_slug}">{m.model_name}</option>')
        
        print()
        print('Testing all models:')
        for i, model in enumerate(models[:5]):
            print(f'{i+1}. slug="{model.canonical_slug}" name="{model.model_name}"')
