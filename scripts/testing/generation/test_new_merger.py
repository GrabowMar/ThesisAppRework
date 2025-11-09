"""Test the new simplified code merger with existing responses."""
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app.services.generation import CodeMerger

def test_backend_merge():
    """Test backend merge with existing openai_codex-mini response."""
    print("=" * 80)
    print("Testing Backend Merge")
    print("=" * 80)
    
    # Load existing response
    response_file = Path('generated/raw/responses/openai_codex-mini/app1148/openai_codex-mini_app1148_backend_20251107T210821_response.json')
    
    if not response_file.exists():
        print(f"❌ Response file not found: {response_file}")
        return False
    
    with open(response_file) as f:
        data = json.load(f)
    
    # Extract LLM content
    content = data['response']['choices'][0]['message']['content']
    print(f"\n📄 LLM Response: {len(content)} chars")
    print(f"   Preview: {content[:150]}...")
    
    # Test code extraction and merge
    merger = CodeMerger()
    app_dir = Path('generated/apps/openai_codex-mini/app1148')
    
    # Create backup of existing file
    app_py = app_dir / 'backend' / 'app.py'
    backup = app_dir / 'backend' / 'app.py.backup'
    if app_py.exists():
        import shutil
        shutil.copy2(app_py, backup)
        print(f"✓ Created backup: {backup}")
    
    # Run merge
    success = merger.merge_backend(app_dir, content)
    
    if success:
        print(f"\n✅ Backend merge succeeded!")
        
        # Check result
        new_code = app_py.read_text(encoding='utf-8')
        print(f"   New app.py: {len(new_code)} chars")
        print(f"   Has Flask app: {'app = Flask' in new_code}")
        print(f"   Has routes: {new_code.count('@app.route')}")
        print(f"   Has if __name__: {'if __name__' in new_code}")
        
        # Show first 500 chars
        print(f"\n📝 First 500 chars of generated code:")
        print("-" * 80)
        print(new_code[:500])
        print("-" * 80)
        
        return True
    else:
        print(f"\n❌ Backend merge failed!")
        return False

def test_frontend_merge():
    """Test frontend merge with existing response."""
    print("\n" + "=" * 80)
    print("Testing Frontend Merge")
    print("=" * 80)
    
    # Load existing response
    response_file = Path('generated/raw/responses/openai_codex-mini/app1148/openai_codex-mini_app1148_frontend_20251107T210855_response.json')
    
    if not response_file.exists():
        print(f"❌ Response file not found: {response_file}")
        return False
    
    with open(response_file) as f:
        data = json.load(f)
    
    # Extract LLM content
    content = data['response']['choices'][0]['message']['content']
    print(f"\n📄 LLM Response: {len(content)} chars")
    print(f"   Preview: {content[:150]}...")
    
    # Test code extraction and merge
    merger = CodeMerger()
    app_dir = Path('generated/apps/openai_codex-mini/app1148')
    
    # Create backup
    app_jsx = app_dir / 'frontend' / 'src' / 'App.jsx'
    backup = app_dir / 'frontend' / 'src' / 'App.jsx.backup'
    if app_jsx.exists():
        import shutil
        shutil.copy2(app_jsx, backup)
        print(f"✓ Created backup: {backup}")
    
    # Run merge
    success = merger.merge_frontend(app_dir, content)
    
    if success:
        print(f"\n✅ Frontend merge succeeded!")
        
        # Check result
        new_code = app_jsx.read_text(encoding='utf-8')
        print(f"   New App.jsx: {len(new_code)} chars")
        print(f"   Has React import: {'import React' in new_code}")
        print(f"   Has API_URL: {'API_URL' in new_code}")
        print(f"   Uses backend:5000: {'backend:5000' in new_code}")
        print(f"   Has export default: {'export default' in new_code}")
        
        # Show first 500 chars
        print(f"\n📝 First 500 chars of generated code:")
        print("-" * 80)
        print(new_code[:500])
        print("-" * 80)
        
        return True
    else:
        print(f"\n❌ Frontend merge failed!")
        return False

if __name__ == '__main__':
    backend_ok = test_backend_merge()
    frontend_ok = test_frontend_merge()
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Backend:  {'✅ PASS' if backend_ok else '❌ FAIL'}")
    print(f"Frontend: {'✅ PASS' if frontend_ok else '❌ FAIL'}")
    print("=" * 80)
    
    sys.exit(0 if (backend_ok and frontend_ok) else 1)
