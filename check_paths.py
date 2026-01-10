
import os
from app.factory import create_app

app = create_app()
with app.app_context():
    print(f"ROOT_PATH: {app.root_path}")
    print(f"DOCS_PATH_CALC: {os.path.abspath(os.path.join(app.root_path, '..', '..', 'docs'))}")
    docs_path = os.path.abspath(os.path.join(app.root_path, '..', '..', 'docs'))
    print(f"DOCS_EXISTS: {os.path.exists(docs_path)}")
    if os.path.exists(docs_path):
        print(f"DOCS_CONTENT: {os.listdir(docs_path)}")
