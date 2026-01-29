import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from app.factory import create_app
from app.extensions import db
from app.models import ModelCapability

def list_models():
    app = create_app()
    with app.app_context():
        models = ModelCapability.query.all()
        print(f"{'Slug':<40} | {'Name':<30} | {'Provider'}")
        print("-" * 80)
        for m in models:
            print(f"{m.canonical_slug:<40} | {m.model_name:<30} | {m.provider}")

if __name__ == "__main__":
    list_models()
