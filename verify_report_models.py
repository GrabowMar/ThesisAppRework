#!/usr/bin/env python3
"""Verify that report modal will show models."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app.factory import create_app
from app.models import ModelCapability, GeneratedApplication, db

def verify():
    """Check that models with apps query returns results."""
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("REPORT MODAL DATA VERIFICATION")
        print("=" * 60)
        
        # This is the exact query used by the reports modal
        models_with_apps = db.session.query(ModelCapability).join(
            GeneratedApplication,
            ModelCapability.canonical_slug == GeneratedApplication.model_slug
        ).distinct().order_by(ModelCapability.provider, ModelCapability.model_name).all()
        
        print(f"\n📊 Models with apps (INNER JOIN query): {len(models_with_apps)}")
        
        if len(models_with_apps) == 0:
            print("\n❌ PROBLEM: Query returns 0 models!")
            print("\nDebugging info:")
            
            # Check totals
            total_models = ModelCapability.query.count()
            total_apps = GeneratedApplication.query.count()
            print(f"   Total models in DB: {total_models}")
            print(f"   Total apps in DB: {total_apps}")
            
            # Check slugs
            if total_apps > 0:
                print("\n   Sample app slugs:")
                for app in GeneratedApplication.query.limit(5).all():
                    print(f"      - {app.model_slug}")
                
                print("\n   Sample model slugs:")
                for model in ModelCapability.query.limit(5).all():
                    print(f"      - {model.canonical_slug}")
                
                # Check for mismatches
                app_slugs = set(a.model_slug for a in GeneratedApplication.query.all())
                model_slugs = set(m.canonical_slug for m in ModelCapability.query.all())
                missing = app_slugs - model_slugs
                if missing:
                    print(f"\n   ⚠️  Apps exist for slugs not in ModelCapability: {missing}")
        else:
            print("\n✅ SUCCESS: Models will appear in report modal!")
            print("\nModels that will be available:")
            for model in models_with_apps:
                apps = GeneratedApplication.query.filter_by(model_slug=model.canonical_slug).all()
                print(f"   • {model.provider} / {model.model_name}")
                print(f"     Slug: {model.canonical_slug}")
                print(f"     Apps: {[a.app_number for a in apps]}")
        
        # Get apps by model mapping
        apps = db.session.query(GeneratedApplication).order_by(
            GeneratedApplication.model_slug, 
            GeneratedApplication.app_number
        ).all()
        
        apps_by_model = {}
        for app in apps:
            if app.model_slug not in apps_by_model:
                apps_by_model[app.model_slug] = []
            apps_by_model[app.model_slug].append(app.app_number)
        
        print(f"\n📋 Apps by model mapping: {len(apps_by_model)} models")
        for slug, app_numbers in sorted(apps_by_model.items()):
            print(f"   {slug}: {app_numbers}")
        
        print("\n" + "=" * 60)

if __name__ == '__main__':
    verify()
