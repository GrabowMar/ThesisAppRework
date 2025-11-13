"""
Sync Generated Apps to Database
================================

Scans the generated/apps/ folder and ensures all apps have database entries.
This is needed for the reports modal to discover which models have generated apps.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.factory import create_app
from app.models import ModelCapability, GeneratedApplication, db
from app.utils.slug_utils import normalize_model_slug, generate_slug_variants

def sync_apps():
    """Scan generated/apps and create missing database records."""
    app = create_app()
    
    with app.app_context():
        apps_dir = Path('generated/apps')
        
        if not apps_dir.exists():
            print(f"❌ {apps_dir} does not exist")
            return
        
        print(f"📁 Scanning {apps_dir}...")
        
        created = 0
        updated = 0
        skipped = 0
        
        # Scan each model directory
        for model_dir in sorted(apps_dir.iterdir()):
            if not model_dir.is_dir():
                continue
            
            filesystem_slug = model_dir.name
            
            # Skip metadata folders
            if filesystem_slug in ['metadata', 'raw', 'capabilities']:
                continue
            
            # Normalize the slug from filesystem
            normalized_slug = normalize_model_slug(filesystem_slug)
            
            # Try to find model in database using normalized slug and variants
            model = ModelCapability.query.filter_by(canonical_slug=normalized_slug).first()
            
            if not model:
                # Try slug variants for backward compatibility
                variants = generate_slug_variants(filesystem_slug)
                for variant in variants:
                    model = ModelCapability.query.filter_by(canonical_slug=variant).first()
                    if model:
                        break
            
            if not model:
                print(f"⚠️  Model not in DB: {filesystem_slug} (normalized: {normalized_slug}) (skipping)")
                continue
            
            # Use the model's canonical slug for consistency
            model_slug = model.canonical_slug
            
            # Scan app folders (app1, app2, etc.)
            app_dirs = sorted([d for d in model_dir.iterdir() if d.is_dir() and d.name.startswith('app')])
            
            for app_dir in app_dirs:
                try:
                    app_number = int(app_dir.name.replace('app', ''))
                except ValueError:
                    continue
                
                # Check if app record exists
                existing = GeneratedApplication.query.filter_by(
                    model_slug=model_slug,
                    app_number=app_number
                ).first()
                
                if existing:
                    skipped += 1
                    continue
                
                # Analyze folder structure
                has_backend = (app_dir / 'backend').exists()
                has_frontend = (app_dir / 'frontend').exists()
                has_compose = (app_dir / 'docker-compose.yml').exists()
                
                # Detect frameworks
                backend_framework = None
                if has_backend:
                    if (app_dir / 'backend' / 'requirements.txt').exists():
                        backend_framework = 'flask'
                    elif (app_dir / 'backend' / 'package.json').exists():
                        backend_framework = 'express'
                
                frontend_framework = None
                if has_frontend:
                    pkg_json = app_dir / 'frontend' / 'package.json'
                    if pkg_json.exists():
                        try:
                            import json
                            pkg_data = json.loads(pkg_json.read_text())
                            deps = pkg_data.get('dependencies', {})
                            if 'react' in deps:
                                frontend_framework = 'react'
                            elif 'vue' in deps:
                                frontend_framework = 'vue'
                            elif '@angular/core' in deps:
                                frontend_framework = 'angular'
                        except:
                            frontend_framework = 'unknown'
                
                # Create database record with normalized slug
                app_record = GeneratedApplication()
                app_record.model_slug = model_slug  # Already normalized from model.canonical_slug
                app_record.app_number = app_number
                app_record.app_type = 'web_app'
                app_record.provider = model.provider
                app_record.has_backend = has_backend
                app_record.has_frontend = has_frontend
                app_record.has_docker_compose = has_compose
                app_record.backend_framework = backend_framework
                app_record.frontend_framework = frontend_framework
                app_record.generation_status = 'completed'
                app_record.container_status = 'unknown'
                
                db.session.add(app_record)
                created += 1
                print(f"✅ Created: {model_slug}/app{app_number}")
        
        # Commit all changes
        if created > 0:
            db.session.commit()
            print(f"\n💾 Committed {created} new records")
        
        print(f"\n📊 Summary:")
        print(f"   Created: {created}")
        print(f"   Skipped (already exist): {skipped}")
        print(f"   Total in DB: {GeneratedApplication.query.count()}")
        
        # Show models with apps
        print(f"\n📋 Models with generated apps:")
        models_with_apps = db.session.query(
            GeneratedApplication.model_slug,
            db.func.count(GeneratedApplication.id).label('count')
        ).group_by(GeneratedApplication.model_slug).all()
        
        for model_slug, count in models_with_apps:
            model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
            model_name = model.model_name if model else model_slug
            print(f"   {model_name}: {count} apps")

if __name__ == '__main__':
    sync_apps()
