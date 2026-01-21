"""Analyze missing apps for deepseek_deepseek-r1-0528."""
import sys
from pathlib import Path
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import GeneratedApplication

app = create_app()
with app.app_context():
    model_slug = 'deepseek_deepseek-r1-0528'
    
    # Get all apps for this model from database
    apps = GeneratedApplication.query.filter_by(model_slug=model_slug).order_by(
        GeneratedApplication.app_number
    ).all()
    
    print(f"=== Analysis for {model_slug} ===\n")
    print(f"Total apps in database: {len(apps)}\n")
    
    # Check filesystem
    generated_dir = Path('generated/apps') / model_slug
    results_dir = Path('results') / model_slug
    
    generated_apps = set()
    results_apps = set()
    
    if generated_dir.exists():
        generated_apps = {int(d.name.replace('app', '')) for d in generated_dir.iterdir() if d.is_dir() and d.name.startswith('app')}
    
    if results_dir.exists():
        results_apps = {int(d.name.replace('app', '')) for d in results_dir.iterdir() if d.is_dir() and d.name.startswith('app')}
    
    print(f"Apps in generated/: {sorted(generated_apps)}")
    print(f"Apps in results/: {sorted(results_apps)}")
    print(f"Missing from results/: {sorted(generated_apps - results_apps)}\n")
    
    # Detailed analysis of each app
    print("=" * 80)
    print("DETAILED APP ANALYSIS")
    print("=" * 80)
    
    for app_num in sorted(generated_apps):
        print(f"\n{'='*80}")
        print(f"APP {app_num}")
        print(f"{'='*80}")
        
        # Database record
        db_app = next((a for a in apps if a.app_number == app_num), None)
        if db_app:
            print(f"\nDatabase Record:")
            print(f"  Template: {db_app.template_slug}")
            print(f"  Status: {db_app.generation_status.value if db_app.generation_status else 'N/A'}")
            print(f"  Failed: {db_app.is_generation_failed}")
            print(f"  Failure Stage: {db_app.failure_stage}")
            print(f"  Error: {db_app.error_message}")
            print(f"  Has Backend: {db_app.has_backend}")
            print(f"  Has Frontend: {db_app.has_frontend}")
        else:
            print(f"\nDatabase Record: NOT FOUND")
        
        # Filesystem - generated/
        gen_path = generated_dir / f'app{app_num}'
        if gen_path.exists():
            print(f"\nGenerated Directory ({gen_path}):")
            backend_dir = gen_path / 'backend'
            frontend_dir = gen_path / 'frontend'
            
            if backend_dir.exists():
                app_py = backend_dir / 'app.py'
                print(f"  Backend: EXISTS")
                if app_py.exists():
                    size = app_py.stat().st_size
                    lines = len(app_py.read_text(encoding='utf-8', errors='ignore').splitlines())
                    print(f"    app.py: {size:,} bytes, {lines} lines")
                else:
                    print(f"    app.py: MISSING")
            else:
                print(f"  Backend: MISSING")
            
            if frontend_dir.exists():
                app_jsx = frontend_dir / 'src' / 'App.jsx'
                print(f"  Frontend: EXISTS")
                if app_jsx.exists():
                    size = app_jsx.stat().st_size
                    lines = len(app_jsx.read_text(encoding='utf-8', errors='ignore').splitlines())
                    print(f"    App.jsx: {size:,} bytes, {lines} lines")
                else:
                    print(f"    App.jsx: MISSING")
            else:
                print(f"  Frontend: MISSING")
        
        # Filesystem - results/
        if app_num in results_apps:
            res_path = results_dir / f'app{app_num}'
            print(f"\nResults Directory ({res_path}): EXISTS")
        else:
            print(f"\nResults Directory: MISSING ⚠️")
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    
    pending = [a for a in apps if a.generation_status.value == 'pending']
    failed = [a for a in apps if a.is_generation_failed]
    completed = [a for a in apps if a.generation_status.value == 'completed']
    
    print(f"\nStatus Breakdown:")
    print(f"  Pending: {len(pending)} apps - {[a.app_number for a in pending]}")
    print(f"  Failed: {len(failed)} apps - {[a.app_number for a in failed]}")
    print(f"  Completed: {len(completed)} apps - {[a.app_number for a in completed]}")
    
    print(f"\nFilesystem vs Database:")
    print(f"  Apps with generated/ but no results/: {sorted(generated_apps - results_apps)}")
    print(f"  Apps with results/ but no generated/: {sorted(results_apps - generated_apps)}")
    
    if pending:
        print(f"\n⚠️  ISSUE: {len(pending)} apps stuck in PENDING status")
        print(f"   Apps: {[a.app_number for a in pending]}")
        print(f"   These apps exist in generated/ but never completed")
