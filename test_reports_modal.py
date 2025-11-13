"""
Test script to debug the reports modal
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app.factory import create_app
from app.models import ModelCapability, GeneratedApplication
from app.extensions import db

def test_models_query():
    """Test the models query used in /reports/new"""
    app = create_app()
    
    with app.app_context():
        print("=" * 80)
        print("Testing /reports/new models query")
        print("=" * 80)
        
        # Query from the route
        models_with_apps = db.session.query(ModelCapability).join(
            GeneratedApplication,
            ModelCapability.canonical_slug == GeneratedApplication.model_slug
        ).distinct().order_by(ModelCapability.provider, ModelCapability.model_name).all()
        
        print(f"\n✓ Found {len(models_with_apps)} models with generated apps:\n")
        
        for model in models_with_apps:
            print(f"  - {model.canonical_slug} ({model.provider}/{model.model_name})")
        
        # Get apps grouped by model
        apps = db.session.query(GeneratedApplication).order_by(
            GeneratedApplication.model_slug, 
            GeneratedApplication.app_number
        ).all()
        
        apps_by_model = {}
        for app in apps:
            if app.model_slug not in apps_by_model:
                apps_by_model[app.model_slug] = []
            apps_by_model[app.model_slug].append(app.app_number)
        
        print(f"\n✓ Apps by model:")
        for slug, app_nums in sorted(apps_by_model.items()):
            print(f"  - {slug}: {app_nums}")
        
        # Convert to dict format used in template
        print(f"\n✓ Converting models to dict format for JSON serialization:\n")
        models_data = []
        for model in models_with_apps:
            model_dict = {
                'id': model.model_id,
                'model_id': model.model_id,
                'canonical_slug': model.canonical_slug,
                'model_slug': model.canonical_slug,
                'slug': model.canonical_slug,
                'model_name': model.model_name,
                'display_name': model.model_name,
                'provider': model.provider
            }
            models_data.append(model_dict)
            print(f"  - {model_dict['canonical_slug']}: {model_dict['model_name']}")
        
        print(f"\n{'=' * 80}")
        print(f"SUMMARY")
        print(f"{'=' * 80}")
        print(f"Models with apps: {len(models_data)}")
        print(f"Total apps: {len(apps)}")
        print(f"Models with app counts: {len(apps_by_model)}")
        
        if len(models_data) == 0:
            print("\n⚠️  WARNING: No models found! This will show 'No models available'")
            print("\nChecking for issues:")
            
            # Check if models exist
            all_models = ModelCapability.query.count()
            print(f"  - Total models in DB: {all_models}")
            
            # Check if apps exist
            all_apps = GeneratedApplication.query.count()
            print(f"  - Total apps in DB: {all_apps}")
            
            if all_apps == 0:
                print("\n❌ No GeneratedApplication records in database!")
                print("   Run: python scripts/sync_generated_apps.py")
            else:
                # Check slug mismatches
                print("\n  Checking for slug mismatches:")
                app_slugs = set(a.model_slug for a in GeneratedApplication.query.all())
                model_slugs = set(m.canonical_slug for m in ModelCapability.query.all())
                
                print(f"\n  App slugs: {sorted(app_slugs)}")
                print(f"\n  Model slugs (first 10): {sorted(model_slugs)[:10]}")
                
                missing = app_slugs - model_slugs
                if missing:
                    print(f"\n  ⚠️  Apps exist for slugs not in ModelCapability: {missing}")
        else:
            print(f"\n✓ SUCCESS: Modal will display {len(models_data)} models")
        
        return models_data, apps_by_model

if __name__ == '__main__':
    test_models_query()
