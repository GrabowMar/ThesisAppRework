#!/usr/bin/env python3
"""
Analyze All Transported Samples
Starts analysis pipeline for all 10 apps from each model with all available tools.
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.factory import create_app
from app.extensions import db
from app.models import ModelCapability, GeneratedApplication, PipelineExecution
from app.services.service_locator import ServiceLocator
from app.constants import AnalysisStatus, AnalysisType
from app.utils.time import utc_now

def get_or_create_model(model_slug: str):
    """Get or create model by slug."""
    model = Model.query.filter_by(model_slug=model_slug).first()
    if not model:
        # Parse slug (format: provider_model-name)
        parts = model_slug.split('_', 1)
        provider = parts[0] if len(parts) > 1 else 'unknown'
        model_name = parts[1] if len(parts) > 1 else model_slug
        
        model = Model(
            model_slug=model_slug,
            provider=provider,
            model_name=model_name
        )
        db.session.add(model)
        db.session.commit()
    return model

def register_apps_from_filesystem():
    """Register all generated apps found in generated/apps directory."""
    generated_dir = Path(__file__).parent.parent / "generated" / "apps"
    
    if not generated_dir.exists():
        print(f"❌ Generated apps directory not found: {generated_dir}")
        return []
    
    registered_apps = []
    
    # Iterate through model folders
    for model_dir in generated_dir.iterdir():
        if not model_dir.is_dir():
            continue
        
        model_slug = model_dir.name
        print(f"\n📦 Processing model: {model_slug}")
        
        model = get_or_create_model(model_slug)
        
        # Iterate through app folders (app1, app2, ..., app10)
        for app_dir in sorted(model_dir.iterdir()):
            if not app_dir.is_dir() or not app_dir.name.startswith('app'):
                continue
            
            try:
                app_number = int(app_dir.name.replace('app', ''))
            except ValueError:
                print(f"  ⚠️  Skipping invalid app folder: {app_dir.name}")
                continue
            
            # Check if app.py exists
            app_file = app_dir / "app.py"
            if not app_file.exists():
                print(f"  ⚠️  Skipping {app_dir.name}: no app.py found")
                continue
            
            # Check if already registered
            existing_app = GeneratedApp.query.filter_by(
                model_id=model.id,
                app_number=app_number
            ).first()
            
            if existing_app:
                print(f"  ✓ {app_dir.name} already registered (ID: {existing_app.id})")
                registered_apps.append(existing_app)
                continue
            
            # Register new app
            app = GeneratedApp(
                model_id=model.id,
                app_number=app_number,
                app_path=str(app_dir.relative_to(Path(__file__).parent.parent)),
                status='generated',
                created_at=utc_now()
            )
            db.session.add(app)
            db.session.flush()  # Get the ID
            
            print(f"  ✓ Registered {app_dir.name} (ID: {app.id})")
            registered_apps.append(app)
    
    db.session.commit()
    return registered_apps

def create_analysis_pipelines(apps):
    """Create analysis pipeline tasks for all apps using all tools."""
    pipeline_service = ServiceLocator.get_pipeline_service()
    
    # All available analysis types
    all_tools = [
        AnalysisType.STATIC_SECURITY,
        AnalysisType.STATIC_QUALITY,
        AnalysisType.STATIC_COMPLEXITY,
        AnalysisType.DYNAMIC_TESTING,
        AnalysisType.PERFORMANCE,
        AnalysisType.AI_REVIEW
    ]
    
    created_pipelines = []
    
    for app in apps:
        # Check if pipeline already exists
        existing_pipeline = PipelineAnalysisTask.query.filter_by(
            app_id=app.id,
            status=AnalysisStatus.PENDING
        ).first()
        
        if existing_pipeline:
            print(f"  ⊘ Pipeline already exists for app {app.model.model_slug}/app{app.app_number}")
            continue
        
        # Create pipeline
        try:
            pipeline = pipeline_service.create_pipeline(
                app_id=app.id,
                analysis_types=all_tools,
                priority=5  # Normal priority
            )
            created_pipelines.append(pipeline)
            print(f"  ✓ Created pipeline for {app.model.model_slug}/app{app.app_number} (Pipeline ID: {pipeline.id})")
        except Exception as e:
            print(f"  ❌ Failed to create pipeline for app {app.id}: {e}")
    
    return created_pipelines

def main():
    """Main function."""
    print("=" * 60)
    print("Starting Analysis for All Transported Samples")
    print("=" * 60)
    
    app = create_app()
    
    with app.app_context():
        print("\n[Step 1/3] Registering apps from filesystem...")
        apps = register_apps_from_filesystem()
        
        if not apps:
            print("\n❌ No apps found to analyze!")
            return 1
        
        print(f"\n✓ Found {len(apps)} apps total")
        
        # Group by model
        from collections import defaultdict
        by_model = defaultdict(list)
        for app in apps:
            by_model[app.model.model_slug].append(app)
        
        print("\nBreakdown by model:")
        for model_slug, model_apps in sorted(by_model.items()):
            print(f"  • {model_slug}: {len(model_apps)} apps")
        
        print("\n[Step 2/3] Creating analysis pipelines...")
        print("Using all available tools:")
        print("  • Static Security Analysis (Bandit, Semgrep)")
        print("  • Static Quality Analysis (Pylint, Flake8, Mypy)")
        print("  • Static Complexity Analysis (Radon)")
        print("  • Dynamic Testing (Pytest, Coverage)")
        print("  • Performance Analysis (Profiling, Benchmarks)")
        print("  • AI Code Review (OpenRouter)")
        print("")
        
        pipelines = create_analysis_pipelines(apps)
        
        if not pipelines:
            print("\n⚠️  No new pipelines created (all may already exist)")
            return 0
        
        print(f"\n✓ Created {len(pipelines)} analysis pipelines")
        
        print("\n[Step 3/3] Starting pipeline execution service...")
        print("The TaskExecutionService will pick up these tasks automatically.")
        print("Check the logs with: docker compose logs -f flask")
        
        print("\n" + "=" * 60)
        print("✓ Analysis Pipeline Started!")
        print("=" * 60)
        print(f"\nTotal pipelines queued: {len(pipelines)}")
        print(f"Total analysis tasks: {len(pipelines) * 6}")  # 6 tools per pipeline
        print("\nMonitor progress:")
        print("  • Web UI: http://localhost:5000/pipelines")
        print("  • Logs: docker compose logs -f flask")
        print("  • Database: SELECT COUNT(*) FROM pipeline_analysis_task WHERE status='COMPLETED';")
        
        return 0

if __name__ == "__main__":
    sys.exit(main())
