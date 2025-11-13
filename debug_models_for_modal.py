#!/usr/bin/env python3
"""Debug models available for report generation modal"""
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app.factory import create_app
from app.models import ModelCapability, GeneratedApplication
from app.extensions import db

def debug_models():
    """Check what models should appear in the modal"""
    app = create_app()
    
    with app.app_context():
        print("=" * 70)
        print("MODELS IN ModelCapability TABLE")
        print("=" * 70)
        
        all_models = db.session.query(ModelCapability).all()
        print(f"Total models in ModelCapability: {len(all_models)}")
        
        for model in all_models[:10]:  # Show first 10
            print(f"  • {model.canonical_slug} - {model.model_name} ({model.provider})")
        
        print("\n" + "=" * 70)
        print("MODELS WITH GENERATED APPLICATIONS")
        print("=" * 70)
        
        # This is the query used in the route
        models_with_apps = db.session.query(ModelCapability).join(
            GeneratedApplication,
            ModelCapability.canonical_slug == GeneratedApplication.model_slug
        ).distinct().order_by(ModelCapability.provider, ModelCapability.model_name).all()
        
        print(f"Models with apps (JOIN result): {len(models_with_apps)}")
        
        for model in models_with_apps:
            print(f"  • {model.canonical_slug} - {model.model_name}")
        
        print("\n" + "=" * 70)
        print("GENERATED APPLICATIONS")
        print("=" * 70)
        
        apps = db.session.query(GeneratedApplication).all()
        print(f"Total apps: {len(apps)}")
        
        # Group by model_slug
        apps_by_model = {}
        for app in apps:
            if app.model_slug not in apps_by_model:
                apps_by_model[app.model_slug] = []
            apps_by_model[app.model_slug].append(app.app_number)
        
        print("\nApps by model_slug:")
        for model_slug, app_numbers in sorted(apps_by_model.items()):
            print(f"  • {model_slug}: {app_numbers}")
        
        print("\n" + "=" * 70)
        print("DIAGNOSIS")
        print("=" * 70)
        
        if len(models_with_apps) == 0:
            print("❌ PROBLEM: No models found in JOIN query")
            print("\nPossible causes:")
            print("1. GeneratedApplication.model_slug doesn't match ModelCapability.canonical_slug")
            print("2. No apps have been generated yet")
            print("3. Slug normalization mismatch")
            
            # Check for mismatches
            print("\nChecking for mismatches:")
            model_slugs_in_capability = set(m.canonical_slug for m in all_models)
            model_slugs_in_apps = set(app.model_slug for app in apps)
            
            print(f"\nSlugs in ModelCapability: {sorted(model_slugs_in_capability)}")
            print(f"\nSlugs in GeneratedApplication: {sorted(model_slugs_in_apps)}")
            
            missing_in_capability = model_slugs_in_apps - model_slugs_in_capability
            if missing_in_capability:
                print(f"\n⚠️ These slugs are in GeneratedApplication but NOT in ModelCapability:")
                for slug in missing_in_capability:
                    print(f"   - {slug}")
        else:
            print(f"✅ Found {len(models_with_apps)} models with apps")

if __name__ == '__main__':
    debug_models()
