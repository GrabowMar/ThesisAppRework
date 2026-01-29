import sys
import os

sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from app.factory import create_app
from app.models import ModelCapability

def list_slugs():
    app = create_app()
    with app.app_context():
        for m in ModelCapability.query.all():
            print(m.canonical_slug)

if __name__ == "__main__":
    list_slugs()
