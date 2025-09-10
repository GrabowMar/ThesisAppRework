#!/usr/bin/env python3
"""
Debug test for analysis_engines import issue with FIXED worker.py path setup
"""

import os
import sys
from pathlib import Path

# Set up the same path context as FIXED worker.py
src_dir = Path(__file__).parent / 'src'
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(src_dir))
os.chdir(str(src_dir))

print(f"Working directory: {os.getcwd()}")
print(f"Python path includes project root: {project_root}")
print(f"Python path includes src dir: {src_dir}")

# Test the import exactly as tasks.py does it
print("\nTesting import like tasks.py with FIXED paths...")

try:
    from app.services.analysis_engines import get_engine
    print("✅ SUCCESS: get_engine imported successfully")
    print(f"get_engine function: {get_engine}")
    
    if get_engine:
        print("✅ get_engine is available")
        try:
            engine = get_engine('security')
            print(f"✅ Security engine created: {engine}")
        except Exception as e:
            print(f"❌ Failed to create engine: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("❌ get_engine is None")
        
except Exception as e:
    print(f"❌ Import failed: {e}")
    import traceback
    traceback.print_exc()
    print("This would cause get_engine = None in tasks.py")

# Test if the Flask app factory works
print("\nTesting Flask app factory...")
try:
    from app.factory import create_app
    app = create_app('debug')
    print(f"✅ Flask app created: {app}")
    
    with app.app_context():
        print("✅ App context active")
        # Test import within app context
        try:
            from app.services.analysis_engines import get_engine
            print("✅ get_engine imported in app context")
            engine = get_engine('security')
            print(f"✅ Security engine created in app context: {engine}")
        except Exception as e:
            print(f"❌ Engine creation failed in app context: {e}")
            import traceback
            traceback.print_exc()
            
except Exception as e:
    print(f"❌ Flask app factory failed: {e}")
    import traceback
    traceback.print_exc()
