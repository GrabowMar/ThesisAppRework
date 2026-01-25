import sys
import os
import types
from unittest.mock import MagicMock, patch

# Add src to python path
sys.path.append(os.path.abspath("src"))

# Helper to mock a package and its submodules
def mock_package(name):
    mock = types.ModuleType(name)
    sys.modules[name] = mock
    return mock

# Mock flask as a package with attributes
mock_flask = mock_package("flask")
mock_flask.Flask = MagicMock
mock_flask.Blueprint = MagicMock
mock_flask.request = MagicMock
mock_flask.current_app = MagicMock
mock_flask.jsonify = MagicMock
mock_flask.g = MagicMock
mock_flask.abort = MagicMock
mock_flask.make_response = MagicMock
mock_flask.Response = MagicMock
mock_flask.url_for = MagicMock

sys.modules["flask.signals"] = MagicMock()
sys.modules["flask.cli"] = MagicMock()
sys.modules["flask.json"] = MagicMock()

# Mock flask_sqlalchemy
mock_fsa = mock_package("flask_sqlalchemy")
mock_fsa.SQLAlchemy = MagicMock

# Mock app dependencies
# We permit 'app' to be loaded normally, but we mock its expensive submodules
# However, app/__init__.py imports app.factory. 
# We must mock app.factory BEFORE app is imported.
sys.modules['app.factory'] = MagicMock()
sys.modules['app.models'] = MagicMock()
sys.modules['app.paths'] = MagicMock()
# sys.modules['app.config'] = MagicMock() # Be careful not to shadow app.services.generation_v2.config if naming conflicts? No.

# Setup paths
from pathlib import Path
ROOT_DIR = Path(os.getcwd())
TEMPLATES_DIR = ROOT_DIR / "misc" / "templates"
REQUIREMENTS_DIR = ROOT_DIR / "misc" / "requirements"
SCAFFOLDING_DIR = ROOT_DIR / "misc" / "scaffolding"

# Configure the mock app.paths
mock_paths = sys.modules['app.paths']
mock_paths.TEMPLATES_V2_DIR = TEMPLATES_DIR
mock_paths.REQUIREMENTS_DIR = REQUIREMENTS_DIR
mock_paths.SCAFFOLDING_DIR = SCAFFOLDING_DIR

# Now import CodeGenerator
try:
    from app.services.generation_v2.code_generator import CodeGenerator
except ImportError as e:
    print(f"ImportError: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

def verify_templates():
    print("Initializing CodeGenerator...")
    with patch('app.services.generation_v2.code_generator.get_api_client') as mock_client:
        try:
            generator = CodeGenerator()
            
            # Test Data
            requirements = {
                "name": "Test App",
                "description": "A test application",
                "backend_requirements": ["Req 1", "Req 2"],
                "admin_requirements": ["Admin Req 1"],
                "api_endpoints": [{"method": "GET", "path": "/api/test", "description": "Test endpoint"}],
                "data_model": {"name": "TestModel", "fields": {"name": "string"}},
                "frontend_requirements": ["Front Req 1"]
            }
            
            backend_context = "Backend context placeholder"
            
            print("\n--- Verifying Backend Prompt ---")
            backend_prompt = generator._build_backend_prompt(requirements)
            
            # Check for strings that we added
            success_backend = True
            if "Public/Guest Access" not in backend_prompt:
                print("FAILURE: 'Public/Guest Access' not found in Backend Prompt")
                success_backend = False
            if "Data Seeding" not in backend_prompt:
                print("FAILURE: 'Data Seeding' not found in Backend Prompt")
                success_backend = False
            
            if success_backend:
                 print("SUCCESS: Backend prompt contains new sections.")
            # else:
            #      print("Snippet:\n" + backend_prompt)

            print("\n--- Verifying Frontend Prompt ---")
            frontend_prompt = generator._build_frontend_prompt(requirements, backend_context)
            
            success_frontend = True
            if "Public View (Guest)" not in frontend_prompt:
                print("FAILURE: 'Public View (Guest)' not found in Frontend Prompt")
                success_frontend = False
            if "UI/UX Enrichment" not in frontend_prompt:
                print("FAILURE: 'UI/UX Enrichment' not found in Frontend Prompt")
                success_frontend = False
                
            if success_frontend:
                 print("SUCCESS: Frontend prompt contains new sections.")
                 
            print("\n--- Verifying System Prompts ---")
            backend_system = generator._get_backend_system_prompt()
            if "GUEST ACCESS" in backend_system and "RICH FEATURES" in backend_system:
                 print("SUCCESS: Backend system prompt updated.")
            else:
                 print("FAILURE: Backend system prompt missing updates.")
                 
            frontend_system = generator._get_frontend_system_prompt()
            if "GUEST ACCESS" in frontend_system and "RICH UI" in frontend_system:
                 print("SUCCESS: Frontend system prompt updated.")
            else:
                 print("FAILURE: Frontend system prompt missing updates.")
                 
        except Exception as e:
            print(f"Runtime Warning: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    verify_templates()
