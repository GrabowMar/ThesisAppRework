import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.factory import create_app
from app.models import ModelCapability

app = create_app()

with app.app_context():
    # Find Claude Haiku 4.5
    model = ModelCapability.query.filter_by(canonical_slug='anthropic_claude-4.5-haiku-20251001').first()
    
    if model:
        print(f"✅ Found: {model.canonical_slug}")
        print(f"   model_id: {model.model_id}")
        print(f"   base_model_id: {model.base_model_id}")
        print(f"   hugging_face_id: {model.hugging_face_id}")
        print(f"   provider: {model.provider}")
    else:
        print("❌ Model not found in database!")
