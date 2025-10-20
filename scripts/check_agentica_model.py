"""Check if agentica-org model exists in database"""
import sys
sys.path.insert(0, 'src')

from app import create_app
from app.models import ModelCapability

app = create_app()
with app.app_context():
    # Try to find the model
    model_slug = 'agentica-org_deepcoder-14b-preview'
    model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
    
    print(f"\n=== Looking for: {model_slug} ===")
    if model:
        print(f"✅ FOUND!")
        print(f"  canonical_slug: {model.canonical_slug}")
        print(f"  model_id: {model.model_id}")
        print(f"  provider: {model.provider}")
        print(f"  model_name: {model.model_name}")
    else:
        print(f"❌ NOT FOUND in database!")
        
        # Check what agentica models exist
        print("\n=== Available agentica-org models ===")
        agentica_models = ModelCapability.query.filter(
            ModelCapability.canonical_slug.like('%agentica%')
        ).all()
        
        if agentica_models:
            for m in agentica_models:
                print(f"  {m.canonical_slug} → {m.model_id}")
        else:
            print("  No agentica-org models found!")
            
        # Check similar models
        print("\n=== Models with 'deepcoder' in name ===")
        deepcoder_models = ModelCapability.query.filter(
            ModelCapability.model_id.like('%deepcoder%')
        ).all()
        
        if deepcoder_models:
            for m in deepcoder_models:
                print(f"  {m.canonical_slug} → {m.model_id}")
        else:
            print("  No deepcoder models found!")
