"""Check if app4658 exists in database."""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import GeneratedApplication
import os

app = create_app()
with app.app_context():
    # Check database
    app_record = GeneratedApplication.query.filter_by(
        model_slug='openai_codex-mini',
        app_number=4658
    ).first()
    
    print('\n📊 Database Check:')
    if app_record:
        print(f'  ✅ Found app record in database:')
        print(f'     ID: {app_record.id}')
        print(f'     Model: {app_record.model_slug}')
        print(f'     App: {app_record.app_number}')
        print(f'     Created: {app_record.created_at}')
    else:
        print('  ❌ No database record for openai_codex-mini/app4658')
    
    # Check filesystem
    app_path = os.path.join('generated', 'apps', 'openai_codex-mini', 'app4658')
    print(f'\n📁 Filesystem Check:')
    if os.path.exists(app_path):
        print(f'  ✅ App directory exists: {app_path}')
    else:
        print(f'  ❌ App directory does NOT exist: {app_path}')
    
    # Count total apps for this model
    total_apps = GeneratedApplication.query.filter_by(model_slug='openai_codex-mini').count()
    print(f'\n📈 Total openai_codex-mini apps in database: {total_apps}')
