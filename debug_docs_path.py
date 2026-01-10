
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

from app.factory import create_app

app = create_app()
print(f"App root path: {app.root_path}")
docs_base = os.path.join(app.root_path, '..', '..', 'docs')
print(f"Docs base (calculated): {docs_base}")
print(f"Docs base (absolute): {os.path.abspath(docs_base)}")
print(f"Docs base exists: {os.path.exists(docs_base)}")

if os.path.exists(docs_base):
    print("Listing docs directory:")
    for f in os.listdir(docs_base):
        print(f" - {f}")
else:
    print("Docs directory not found!")
