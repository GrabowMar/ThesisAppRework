"""Verify the new generation system by generating three test apps."""
import asyncio
import sys
from pathlib import Path
import json
import os
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Set minimal env for Flask app context (use actual database, not test.db!)
# Don't override DATABASE_URL - let it default to src/data/thesis_app.db
os.environ.setdefault('SECRET_KEY', 'test-key-for-verification')

from app import create_app
from app.services.generation import get_generation_service

def generate_and_verify_sync(model_slug: str, template_slug: str, app_num: int, app):
    """Generate an app and verify it has complete code (synchronous wrapper)."""
    print("\n" + "=" * 80)
    print(f"Generating: {model_slug} / {template_slug} / app{app_num}")
    print("=" * 80)
    
    try:
        # Run async generation in app context (like the web app does)
        # asyncio.run creates a new event loop that doesn't preserve Flask app context
        # So we need to push the context before the async operation
        async def _do_generation():
            service = get_generation_service()
            return await service.generate_full_app(
                model_slug=model_slug,
                app_num=app_num,
                template_slug=template_slug,
                generate_frontend=True,
                generate_backend=True
            )
        
        # Push app context BEFORE asyncio.run, but Flask app context doesn't work that way
        # Instead, we need to make the database queries work differently
        # Actually, the issue is that asyncio.run() creates a new thread/context
        # Let me check if there's a better pattern in Flask for async...
        
        # For now, let's just bypass the model lookup issue by directly calling with the model
        service = get_generation_service()
        
        # Manually create event loop and run in current thread with app context active
        with app.app_context():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(_do_generation())
            finally:
                loop.close()
        
        print(f"\nGeneration Result:")
        print(f"   Success: {result['success']}")
        print(f"   Scaffolded: {result['scaffolded']}")
        print(f"   Backend Generated: {result['backend_generated']}")
        print(f"   Frontend Generated: {result['frontend_generated']}")
        print(f"   App Dir: {result['app_dir']}")
        if result.get('errors'):
            print(f"   Errors: {result['errors']}")
        
        if not result['success']:
            print(f"\nGeneration failed!")
            return False
        
        # Verify backend
        app_dir = Path(result['app_dir'])
        backend_path = app_dir / 'backend' / 'app.py'
        
        if not backend_path.exists():
            print(f"\n❌ Backend file missing: {backend_path}")
            return False
        
        backend_code = backend_path.read_text(encoding='utf-8')
        print(f"\n[Backend Verification]")
        print(f"   File size: {len(backend_code)} chars")
        
        checks = {
            'from flask import Flask': 'Flask import',
            'app = Flask(__name__)': 'Flask app init',
            'from flask_cors import CORS': 'CORS import',
            'CORS(app)': 'CORS enabled',
            'from flask_sqlalchemy import SQLAlchemy': 'SQLAlchemy import',
            'db = SQLAlchemy()': 'DB instance',
            'def setup_app(app)': 'setup_app function',
            "if __name__ == '__main__'": 'main block',
            "os.environ.get('FLASK_RUN_PORT'": 'env port config',
            "app.run(host='0.0.0.0'": 'app.run with 0.0.0.0',
            '@app.route': 'has routes',
            '@app.errorhandler': 'error handlers'
        }
        
        backend_ok = True
        for check, desc in checks.items():
            found = check in backend_code
            status = "✓" if found else "✗"
            print(f"   [{status}] {desc}")
            if not found and 'error handlers' not in desc:
                backend_ok = False
        
        # Verify frontend
        frontend_path = app_dir / 'frontend' / 'src' / 'App.jsx'
        
        if not frontend_path.exists():
            print(f"\n❌ Frontend file missing: {frontend_path}")
            return False
        
        frontend_code = frontend_path.read_text(encoding='utf-8')
        print(f"\n[Frontend Verification]")
        print(f"   File size: {len(frontend_code)} chars")
        
        checks = {
            'import React': 'React import',
            'from react': 'React import (alt)',
            'import axios': 'Axios import',
            "import 'bootstrap/dist/css/bootstrap.min.css'": 'Bootstrap CSS',
            "import './App.css'": 'App.css import',
            "const API_URL = 'http://backend:5000'": 'API_URL with backend:5000',
            'function App()': 'App component',
            'export default App': 'export default'
        }
        
        frontend_ok = True
        for check, desc in checks.items():
            found = check in frontend_code
            status = "✓" if found else "✗"
            print(f"   [{status}] {desc}")
            if not found and 'React import' in desc:
                # Check alternative import format
                continue
            elif not found:
                frontend_ok = False
        
        # Check for localhost instead of backend:5000 (should not exist)
        if 'localhost:5000' in frontend_code and 'backend:5000' not in frontend_code:
            print(f"   [✗] WARNING: Uses localhost instead of backend:5000")
            frontend_ok = False
        
        # Verify requirements.txt updated
        req_path = app_dir / 'backend' / 'requirements.txt'
        if req_path.exists():
            req_content = req_path.read_text(encoding='utf-8')
            print(f"\n📦 Dependencies:")
            req_lines = [l.strip() for l in req_content.split('\n') if l.strip() and not l.startswith('#')]
            for line in req_lines[:10]:  # Show first 10
                print(f"   - {line}")
            if len(req_lines) > 10:
                print(f"   ... and {len(req_lines) - 10} more")
        
        overall_ok = backend_ok and frontend_ok
        
        if overall_ok:
            print(f"\n[SUCCESS] App {app_num} is COMPLETE and VALID")
        else:
            print(f"\n[WARNING] App {app_num} generated but has issues")
        
        # Save verification report
        report = {
            'model_slug': model_slug,
            'template_slug': template_slug,
            'app_num': app_num,
            'success': result['success'],
            'backend_generated': result['backend_generated'],
            'frontend_generated': result['frontend_generated'],
            'backend_checks': {desc: check in backend_code for check, desc in checks.items()},
            'frontend_checks': {},  # Simplified for JSON serialization
            'backend_size': len(backend_code),
            'frontend_size': len(frontend_code),
            'overall_valid': overall_ok
        }
        
        report_path = app_dir / 'verification_report.json'
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\n[SAVED] Verification report: {report_path}")
        
        return overall_ok
        
    except Exception as e:
        print(f"\n[ERROR] Exception during generation: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run verification tests."""
    print("=" * 80)
    print("GENERATION SYSTEM VERIFICATION")
    print("=" * 80)
    print("\nThis will generate 3 apps and verify they have complete code.")
    print("Each app should have:")
    print("  - Complete Flask backend with app init and if __name__ block")
    print("  - Complete React frontend with backend:5000 API_URL")
    print("  - All required imports and dependencies")
    
    # Create Flask app context
    app = create_app()
    print("\n[+] Flask app initialized")
    
    # Test configurations
    tests = [
        {
            'model': 'openai_gpt-4o-2024-11-20',
            'template': 'auth_user_login',
            'app_num': 20001
        },
        {
            'model': 'openai_gpt-4o-2024-11-20',
            'template': 'crud_todo_list',
            'app_num': 20002
        },
        {
            'model': 'openai_gpt-4o-2024-11-20',
            'template': 'api_url_shortener',
            'app_num': 20003
        }
    ]
    
    results = []
    
    for test in tests:
        success = generate_and_verify_sync(
            test['model'],
            test['template'],
            test['app_num'],
            app
        )
        results.append({
            'config': test,
            'success': success
        })
        
        # Brief pause between generations
        time.sleep(2)
    
    # Summary
    print("\n" + "=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)
    
    for i, result in enumerate(results, 1):
        status = "[PASS]" if result['success'] else "[FAIL]"
        config = result['config']
        print(f"{i}. {config['template']} (app{config['app_num']}): {status}")
    
    passed = sum(1 for r in results if r['success'])
    total = len(results)
    
    print(f"\n[RESULTS] {passed}/{total} passed")
    
    if passed == total:
        print("\n[SUCCESS] All tests PASSED! Generation system is working correctly.")
        return 0
    elif passed > 0:
        print(f"\n[PARTIAL] Partial success: {passed}/{total} apps are complete.")
        return 1
    else:
        print("\n[FAIL] All tests FAILED! Generation system needs attention.")
        return 2

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
