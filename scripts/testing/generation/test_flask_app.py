"""Quick test to see if we can manually fix the generated backend to work."""
import sys
from pathlib import Path

# Read the generated code
app_py = Path('generated/apps/openai_codex-mini/app1148/backend/app.py')
code = app_py.read_text(encoding='utf-8')

print("Original code length:", len(code))
print("Has 'app = Flask':", 'app = Flask' in code)
print("Has 'if __name__':", 'if __name__' in code)

# Add Flask app initialization and if __name__ block
if 'app = Flask' not in code:
    # Insert Flask app initialization after imports
    lines = code.split('\n')
    
    # Find where to insert (after last import or after logging setup)
    insert_pos = 0
    for i, line in enumerate(lines):
        if line.startswith('import ') or line.startswith('from '):
            insert_pos = i + 1
        elif 'logger.addHandler' in line:
            insert_pos = i + 1
            break
    
    # Insert Flask app setup
    flask_setup = """
from flask import Flask
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
"""
    
    lines.insert(insert_pos, flask_setup)
    
    # Add if __name__ block at the end
    main_block = """

if __name__ == '__main__':
    import os
    if 'setup_app' in globals():
        setup_app(app)
    port = int(os.environ.get('FLASK_RUN_PORT', os.environ.get('PORT', 5000)))
    app.run(host='0.0.0.0', port=port, debug=True)
"""
    
    lines.append(main_block)
    
    # Write modified code
    modified_code = '\n'.join(lines)
    app_py.write_text(modified_code, encoding='utf-8')
    
    print(f"\n✅ Added Flask app initialization and if __name__ block")
    print(f"   New length: {len(modified_code)}")

# Try to import it
sys.path.insert(0, str(app_py.parent))
try:
    import app as flask_app
    print("\n✅ Flask app imports successfully!")
    print(f"   App object: {flask_app.app}")
    print(f"   Routes: {list(flask_app.app.url_map.iter_rules())[:5]}")
except Exception as e:
    print(f"\n❌ Failed to import: {e}")
    import traceback
    traceback.print_exc()
