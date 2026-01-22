#!/usr/bin/env python3
"""
Analyze Existing Apps Script
Creates analysis tasks for all apps found in generated/apps directory.
"""

import sys
import os
from pathlib import Path
from collections import defaultdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.factory import create_app
from app.extensions import db
from app.models import GeneratedApplication, AnalysisTask
from app.services.service_locator import ServiceLocator
from app.constants import AnalysisStatus, AnalysisType
from app.utils.time import utc_now


def scan_and_register_apps():
    """Scan filesystem and register any apps not in database."""
    generated_dir = Path(__file__).parent.parent / "generated" / "apps"
    
    if not generated_dir.exists():
        print(f"❌ Generated apps directory not found: {generated_dir}")
        return []
    
    registered_apps = []
    new_apps = []
    
    # Iterate through model folders
    for model_dir in sorted(generated_dir.iterdir()):
        if not model_dir.is_dir():
            continue
        
        model_slug = model_dir.name
        print(f"\n📦 Processing model: {model_slug}")
        
        # Parse provider from slug (format: provider_model-name)
        parts = model_slug.split('_', 1)
        provider = parts[0] if len(parts) > 1 else 'unknown'
        
        # Iterate through app folders (app1, app2, ..., app10)
        for app_dir in sorted(model_dir.iterdir()):
            if not app_dir.is_dir() or not app_dir.name.startswith('app'):
                continue
            
            try:
                app_number = int(app_dir.name.replace('app', ''))
            except ValueError:
                print(f"  ⚠️  Skipping invalid app folder: {app_dir.name}")
                continue
            
            # Check if app.py exists (either at root or in backend/)
            app_file = app_dir / "app.py"
            if not app_file.exists():
                app_file = app_dir / "backend" / "app.py"
            if not app_file.exists():
                print(f"  ⚠️  Skipping {app_dir.name}: no app.py found")
                continue
            
            # Check if already registered
            existing_app = GeneratedApplication.query.filter_by(
                model_slug=model_slug,
                app_number=app_number,
                version=1
            ).first()
            
            if existing_app:
                print(f"  ✓ {app_dir.name} already registered (ID: {existing_app.id})")
                registered_apps.append(existing_app)
                continue
            
            # Detect app structure
            has_backend = app_file.exists()
            has_frontend = (app_dir / "frontend" / "package.json").exists()
            has_docker_compose = (app_dir / "docker-compose.yml").exists()
            
            # Detect frameworks
            backend_framework = None
            if has_backend:
                content = app_file.read_text(encoding='utf-8', errors='ignore')
                if 'from flask' in content.lower():
                    backend_framework = 'Flask'
                elif 'fastapi' in content.lower():
                    backend_framework = 'FastAPI'
            
            frontend_framework = None
            if has_frontend:
                pkg_json = app_dir / "frontend" / "package.json"
                if pkg_json.exists():
                    pkg_content = pkg_json.read_text(encoding='utf-8', errors='ignore')
                    if 'react' in pkg_content.lower():
                        frontend_framework = 'React'
                    elif 'vue' in pkg_content.lower():
                        frontend_framework = 'Vue'
            
            # Register new app
            app = GeneratedApplication(
                model_slug=model_slug,
                app_number=app_number,
                version=1,
                app_type='custom',
                provider=provider,
                generation_status=AnalysisStatus.COMPLETED,
                has_backend=has_backend,
                has_frontend=has_frontend,
                has_docker_compose=has_docker_compose,
                backend_framework=backend_framework,
                frontend_framework=frontend_framework,
                container_status='stopped',
                created_at=utc_now()
            )
            db.session.add(app)
            db.session.flush()  # Get the ID
            
            print(f"  ✓ Registered {app_dir.name} (ID: {app.id})")
            registered_apps.append(app)
            new_apps.append(app)
    
    db.session.commit()
    return registered_apps, new_apps


def create_analysis_tasks_for_apps(apps):
    """Create analysis tasks for apps using all available tools."""
    from app.services.task_service import AnalysisTaskService
    
    # Define analysis configurations with tools
    analysis_configs = [
        {
            'name': 'security',
            'tools': ['bandit', 'semgrep'],
            'description': 'Security analysis'
        },
        {
            'name': 'quality',
            'tools': ['pylint', 'flake8', 'mypy'],
            'description': 'Code quality analysis'
        },
        {
            'name': 'complexity',
            'tools': ['radon'],
            'description': 'Complexity analysis'
        },
        {
            'name': 'testing',
            'tools': ['pytest', 'coverage'],
            'description': 'Dynamic testing'
        },
        {
            'name': 'performance',
            'tools': ['locust', 'profiling'],
            'description': 'Performance analysis'
        },
        {
            'name': 'ai_review',
            'tools': ['openrouter'],
            'description': 'AI code review'
        }
    ]
    
    created_tasks = []
    
    for app in apps:
        # Create task for each analysis configuration
        for config in analysis_configs:
            # Check if task already exists
            existing_task = AnalysisTask.query.filter_by(
                target_model=app.model_slug,
                target_app_number=app.app_number,
                task_name=f"{config['name']}:{app.model_slug}:app{app.app_number}",
                is_main_task=True
            ).first()
            
            if existing_task and existing_task.status == AnalysisStatus.PENDING:
                print(f"  ⊘ {config['name']} task already exists for {app.model_slug}/app{app.app_number}")
                continue
            
            try:
                task = AnalysisTaskService.create_task(
                    model_slug=app.model_slug,
                    app_number=app.app_number,
                    tools=config['tools'],
                    priority='normal',
                    task_name=f"{config['name']}:{app.model_slug}:app{app.app_number}",
                    description=f"{config['description']} for {app.model_slug}/app{app.app_number}",
                    dispatch=False  # Don't dispatch to Celery, let TaskExecutionService handle it
                )
                created_tasks.append(task)
                print(f"  ✓ Created {config['name']} task for {app.model_slug}/app{app.app_number} (Task ID: {task.task_id})")
            except Exception as e:
                print(f"  ❌ Failed to create {config['name']} task for {app.model_slug}/app{app.app_number}: {e}")
    
    return created_tasks


def main():
    """Main function."""
    print("=" * 60)
    print("Analyzing All Existing Apps")
    print("=" * 60)
    
    app = create_app()
    
    with app.app_context():
        print("\n[Step 1/3] Scanning and registering apps...")
        all_apps, new_apps = scan_and_register_apps()
        
        if not all_apps:
            print("\n❌ No apps found to analyze!")
            return 1
        
        print(f"\n✓ Found {len(all_apps)} apps total ({len(new_apps)} newly registered)")
        
        # Group by model
        by_model = defaultdict(list)
        for app in all_apps:
            by_model[app.model_slug].append(app)
        
        print("\nBreakdown by model:")
        for model_slug, model_apps in sorted(by_model.items()):
            print(f"  • {model_slug}: {len(model_apps)} apps")
        
        print("\n[Step 2/3] Creating analysis tasks...")
        print("Available analysis types:")
        print("  • Static Security Analysis (Bandit, Semgrep)")
        print("  • Static Quality Analysis (Pylint, Flake8, Mypy)")
        print("  • Static Complexity Analysis (Radon)")
        print("  • Dynamic Testing (Pytest, Coverage)")
        print("  • Performance Analysis (Locust, Profiling)")
        print("  • AI Code Review (OpenRouter)")
        print("")
        
        tasks = create_analysis_tasks_for_apps(all_apps)
        
        if not tasks:
            print("\n⚠️  No new tasks created (all may already exist)")
            return 0
        
        print(f"\n✓ Created {len(tasks)} analysis tasks")
        
        print("\n[Step 3/3] Task execution...")
        print("The TaskExecutionService will pick up these tasks automatically.")
        print("Check the logs with: docker compose logs -f celery-worker")
        
        print("\n" + "=" * 60)
        print("✓ Analysis Tasks Created!")
        print("=" * 60)
        print(f"\nTotal tasks queued: {len(tasks)}")
        print(f"Apps to analyze: {len(all_apps)}")
        print("\nMonitor progress:")
        print("  • Web UI: http://localhost:5000/tasks")
        print("  • Logs: docker compose logs -f celery-worker")
        print("  • Database: SELECT COUNT(*) FROM analysis_tasks WHERE status='COMPLETED';")
        
        return 0


if __name__ == "__main__":
    sys.exit(main())
