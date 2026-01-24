import asyncio
import os
import sys
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to python path
project_root = Path(os.getcwd())
sys.path.append(str(project_root / 'src'))

# Attempt to load .env if not loaded
env_path = project_root / '.env'
if env_path.exists():
    print(f"Loading .env from {env_path}")
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                if key not in os.environ:
                    os.environ[key] = val.strip('"\'')

from app.services.generation_v2.code_generator import CodeGenerator
from app.services.generation_v2.config import GenerationConfig
from app.factory import create_cli_app

# Mock DB dependencies
# We need to patch ModelCapability used in _get_openrouter_model and _get_model_context_window
mock_model_query = MagicMock()
mock_db_model = MagicMock()
mock_db_model.get_openrouter_model_id.return_value = "anthropic/claude-3-5-sonnet"
mock_db_model.context_window = 200000
mock_model_query.filter_by.return_value.first.return_value = mock_db_model

async def main():
    if 'OPENROUTER_API_KEY' not in os.environ:
        print("ERROR: OPENROUTER_API_KEY not found in environment or .env file.")
        print("Skipping generation to avoid crash.")
        return

    # Use CLI app context to ensure DB and config is ready
    app = create_cli_app()
    with app.app_context():
        # Apply patch INSIDE the app context to avoid RuntimeError during lookup
        with patch('app.models.ModelCapability.query', mock_model_query):
            generator = CodeGenerator()
            print("CodeGenerator ready.")
            
            apps_to_gen = [
                {'template': 'crud_todo_list', 'app_num': 1},
                {'template': 'productivity_notes', 'app_num': 2}
            ]
            
            for app_def in apps_to_gen:
                slug = app_def['template']
                num = app_def['app_num']
                print(f"\n--- Generating {slug} (App {num}) ---")
                
                config = GenerationConfig(
                    model_slug='anthropic_claude-3-5-sonnet',
                    template_slug=slug,
                    app_num=num,
                    save_artifacts=True
                )
                
                try:
                    results = await generator.generate(config)
                    
                    # Save files
                    app_dir = config.get_app_dir(project_root / 'generated' / 'apps')
                    if app_dir.exists():
                        shutil.rmtree(app_dir)
                    app_dir.mkdir(parents=True)
                    
                    # Backend
                    backend_dir = app_dir / 'backend'
                    backend_dir.mkdir()
                    (backend_dir / 'app.py').write_text(results['backend'], encoding='utf-8')
                    (backend_dir / 'requirements.txt').write_text("flask\nflask-sqlalchemy\nflask-cors\npytest\n", encoding='utf-8')
                    
                    # Frontend
                    frontend_dir = app_dir / 'frontend' / 'src'
                    frontend_dir.mkdir(parents=True)
                    (frontend_dir / 'App.jsx').write_text(results['frontend'], encoding='utf-8')
                    
                    print(f"SUCCESS: App generated at {app_dir}")
                    print(f"Backend size: {len(results['backend'])} chars")
                    print(f"Frontend size: {len(results['frontend'])} chars")
                    
                except Exception as e:
                    print(f"FAILED: {e}")
                    import traceback
                    traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
