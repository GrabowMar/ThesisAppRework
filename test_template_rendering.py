#!/usr/bin/env python3
"""
Minimal Flask app to test model template rendering
"""

import sys
sys.path.append('src')
from flask import Flask, render_template_string
from models import ModelCapability
from extensions import db
import os

# Set up minimal Flask app
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///C:/Users/grabowmar/Desktop/ThesisAppRework/instance/app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Set template directory
app.template_folder = 'src/templates'

# Initialize database
db.init_app(app)

# Minimal template for testing
TEMPLATE = '''
<select name="target_models" multiple>
    {% for model in available_models %}
    <option value="{{ model.canonical_slug }}">{{ model.model_name }}</option>
    {% endfor %}
</select>
'''

@app.route('/')
def test_models():
    models = ModelCapability.query.all()
    print(f"Found {len(models)} models")
    if models:
        for i, model in enumerate(models[:3]):
            print(f"Model {i+1}: slug='{model.canonical_slug}', name='{model.model_name}'")
    
    html = render_template_string(TEMPLATE, available_models=models)
    return f"<pre>{html}</pre>"

if __name__ == '__main__':
    with app.app_context():
        print("Testing template rendering...")
        models = ModelCapability.query.all()
        print(f"Found {len(models)} models in context")
        
        # Test template rendering
        html = render_template_string(TEMPLATE, available_models=models)
        print("\nRendered HTML:")
        print(html)
        
        # Check for empty values
        if 'value=""' in html:
            print("\n❌ Found empty values in rendered HTML!")
            print("First model debug:")
            if models:
                m = models[0]
                print(f"  Type: {type(m)}")
                print(f"  Slug: '{m.canonical_slug}' (type: {type(m.canonical_slug)})")
                print(f"  Name: '{m.model_name}' (type: {type(m.model_name)})")
        else:
            print("\n✅ All values populated correctly!")
