#!/usr/bin/env python
"""Sync database port configurations from generated app .env files.

This script scans all generated apps and updates the database
to match the ports actually configured in their .env files.
"""
import sys
from pathlib import Path

sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import PortConfiguration
from app.extensions import db

def parse_env_file(env_path: Path):
    """Parse .env file and extract port configuration."""
    backend_port = None
    frontend_port = None
    
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('BACKEND_PORT='):
                backend_port = int(line.split('=', 1)[1].strip())
            elif line.startswith('FRONTEND_PORT='):
                frontend_port = int(line.split('=', 1)[1].strip())
    
    return backend_port, frontend_port

def main():
    app = create_app('default')
    generated_apps_dir = Path('generated/apps')
    
    if not generated_apps_dir.exists():
        print(f"Generated apps directory not found: {generated_apps_dir}")
        return
    
    with app.app_context():
        updated = 0
        created = 0
        errors = []
        
        # Scan all model directories
        for model_dir in generated_apps_dir.iterdir():
            if not model_dir.is_dir():
                continue
            
            model_slug = model_dir.name
            
            # Scan all app directories
            for app_dir in model_dir.iterdir():
                if not app_dir.is_dir() or not app_dir.name.startswith('app'):
                    continue
                
                try:
                    app_number = int(app_dir.name[3:])  # Extract number from "app1", "app2", etc.
                except ValueError:
                    continue
                
                env_file = app_dir / '.env'
                if not env_file.exists():
                    continue
                
                try:
                    backend_port, frontend_port = parse_env_file(env_file)
                    
                    if backend_port is None or frontend_port is None:
                        print(f"⚠️  {model_slug}/app{app_number}: Missing port configuration in .env")
                        continue
                    
                    # Check database
                    config = PortConfiguration.query.filter_by(model=model_slug, app_num=app_number).first()
                    
                    if config:
                        # Update if different
                        if config.backend_port != backend_port or config.frontend_port != frontend_port:
                            print(f"📝 {model_slug}/app{app_number}: "
                                  f"Updating ports from {config.backend_port}/{config.frontend_port} "
                                  f"to {backend_port}/{frontend_port}")
                            config.backend_port = backend_port
                            config.frontend_port = frontend_port
                            updated += 1
                        else:
                            print(f"✅ {model_slug}/app{app_number}: Ports already correct ({backend_port}/{frontend_port})")
                    else:
                        # Create new entry
                        print(f"➕ {model_slug}/app{app_number}: Creating port configuration ({backend_port}/{frontend_port})")
                        config = PortConfiguration()
                        config.model = model_slug
                        config.app_num = app_number
                        config.backend_port = backend_port
                        config.frontend_port = frontend_port
                        config.is_available = True
                        db.session.add(config)
                        created += 1
                    
                except Exception as e:
                    error_msg = f"Error processing {model_slug}/app{app_number}: {str(e)}"
                    errors.append(error_msg)
                    print(f"❌ {error_msg}")
        
        # Commit changes
        if updated > 0 or created > 0:
            try:
                db.session.commit()
                print(f"\n✨ Successfully synced port configurations:")
                print(f"   Created: {created}")
                print(f"   Updated: {updated}")
                print(f"   Errors: {len(errors)}")
            except Exception as e:
                db.session.rollback()
                print(f"\n❌ Failed to commit changes: {str(e)}")
        else:
            print("\n✅ No changes needed - all ports already match!")

if __name__ == '__main__':
    main()
