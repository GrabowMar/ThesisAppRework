"""Check Grok model IDs in database"""
import sys
sys.path.insert(0, 'src')

from app import create_app
from app.models import ModelCapability

app = create_app()
with app.app_context():
    models = ModelCapability.query.filter(
        ModelCapability.canonical_slug.like('%grok%')
    ).all()
    
    print('\n=== Grok Models in DB ===')
    for m in models:
        print(f'  Slug: {m.canonical_slug:50} | ID: {m.model_id}')
    
    print('\n=== Testing agentic-org models ===')
    agentic = ModelCapability.query.filter(
        ModelCapability.canonical_slug.like('%agentic%')
    ).all()
    for m in agentic:
        print(f'  Slug: {m.canonical_slug:50} | ID: {m.model_id}')
