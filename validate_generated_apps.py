"""Validate generated applications for common issues"""
import ast
import json
import re
from pathlib import Path

def check_backend(file_path):
    """Check backend Python file for issues"""
    issues = []
    
    try:
        code = file_path.read_text(encoding='utf-8')
        
        # Syntax check
        try:
            ast.parse(code)
        except SyntaxError as e:
            issues.append(f"Syntax error at line {e.lineno}: {e.msg}")
            return issues  # Can't continue with syntax errors
        
        # Structure checks
        if 'db = SQLAlchemy()' not in code:
            issues.append("Missing 'db = SQLAlchemy()' instance")
        
        if 'def setup_app' not in code:
            issues.append("Missing 'setup_app()' function")
        
        route_count = code.count('@app.route')
        if route_count < 4:
            issues.append(f"Only {route_count} routes (expected 4+ for CRUD)")
        
        # Check for common mistakes
        if 'db.create_all()' in code and 'with app.app_context():' not in code:
            issues.append("db.create_all() called outside app context")
        
        if 'jsonify' in code and 'from flask import' not in code[:500]:
            issues.append("Uses jsonify but may not import it")
            
        # Check response format consistency
        if 'response.data.todos' in code:  # Frontend expects this
            pass  # Good
        elif route_count > 0:
            # Check if routes return proper format
            if not re.search(r"'todos':\s*\[", code):
                issues.append("Backend may not return 'todos' array expected by frontend")
                
    except Exception as e:
        issues.append(f"Error reading file: {str(e)}")
    
    return issues

def check_frontend(file_path):
    """Check frontend React file for issues"""
    issues = []
    
    try:
        code = file_path.read_text(encoding='utf-8')
        
        # Basic structure checks
        if 'export default' not in code:
            issues.append("Missing 'export default' statement")
        
        if 'import React' not in code and 'import {' not in code:
            issues.append("Missing React import")
        
        # API integration checks
        if 'axios' not in code and 'fetch' not in code:
            issues.append("No HTTP client (axios/fetch) found")
        
        # Check API URL
        api_url_match = re.search(r"API_URL\s*=\s*['\"]([^'\"]+)['\"]", code)
        if api_url_match:
            api_url = api_url_match.group(1)
            if 'localhost' in api_url:
                issues.append(f"API_URL uses localhost instead of 'backend' service: {api_url}")
            elif 'backend' not in api_url and '127.0.0.1' not in api_url:
                issues.append(f"API_URL may be incorrect: {api_url}")
        
        # Check for common React mistakes
        if code.count('useState') > 10:
            issues.append("Very complex state management - consider refactoring")
        
    except Exception as e:
        issues.append(f"Error reading file: {str(e)}")
    
    return issues

def check_docker_compose(file_path):
    """Check docker-compose.yml for issues"""
    issues = []
    
    try:
        import yaml
        with open(file_path, 'r') as f:
            compose = yaml.safe_load(f)
        
        # Check services exist
        if 'services' not in compose:
            issues.append("No services defined")
            return issues
        
        services = compose['services']
        
        # Check backend service
        if 'backend' not in services:
            issues.append("Missing 'backend' service")
        else:
            backend = services['backend']
            if 'ports' not in backend:
                issues.append("Backend service has no ports exposed")
            if 'environment' in backend:
                env = backend['environment']
                if isinstance(env, list):
                    db_uri = [e for e in env if 'SQLALCHEMY_DATABASE_URI' in str(e)]
                    if db_uri and 'sqlite:////tmp' in str(db_uri[0]):
                        issues.append("Backend uses /tmp for SQLite - data will be lost on restart")
        
        # Check frontend service
        if 'frontend' not in services:
            issues.append("Missing 'frontend' service")
        else:
            frontend = services['frontend']
            if 'depends_on' not in frontend:
                issues.append("Frontend doesn't depend on backend")
        
    except ImportError:
        issues.append("PyYAML not installed - can't validate YAML")
    except Exception as e:
        issues.append(f"Error parsing docker-compose.yml: {str(e)}")
    
    return issues

def main():
    apps_dir = Path('generated/apps/openai_gpt-4o-mini')
    
    if not apps_dir.exists():
        print(f"Directory not found: {apps_dir}")
        return
    
    all_issues = {}
    
    for app_dir in sorted(apps_dir.iterdir()):
        if not app_dir.is_dir():
            continue
        
        print(f"\n{'='*80}")
        print(f"Checking: {app_dir.name}")
        print(f"{'='*80}")
        
        issues = {}
        
        # Check backend
        backend_file = app_dir / 'backend' / 'app.py'
        if backend_file.exists():
            backend_issues = check_backend(backend_file)
            if backend_issues:
                issues['backend'] = backend_issues
        else:
            issues['backend'] = ['backend/app.py not found']
        
        # Check frontend
        frontend_file = app_dir / 'frontend' / 'src' / 'App.jsx'
        if frontend_file.exists():
            frontend_issues = check_frontend(frontend_file)
            if frontend_issues:
                issues['frontend'] = frontend_issues
        else:
            issues['frontend'] = ['frontend/src/App.jsx not found']
        
        # Check docker-compose
        compose_file = app_dir / 'docker-compose.yml'
        if compose_file.exists():
            compose_issues = check_docker_compose(compose_file)
            if compose_issues:
                issues['docker-compose'] = compose_issues
        
        # Print results
        if issues:
            all_issues[app_dir.name] = issues
            for component, component_issues in issues.items():
                print(f"\n{component.upper()}:")
                for issue in component_issues:
                    print(f"  [X] {issue}")
        else:
            print("\n[OK] No issues found!")
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    
    if all_issues:
        print(f"\nFound issues in {len(all_issues)} app(s):")
        for app_name in all_issues:
            print(f"  - {app_name}")
    else:
        print("\n✓ All apps validated successfully!")
    
    return all_issues

if __name__ == '__main__':
    main()
