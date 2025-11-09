"""Quick script to check model existence in database."""
import sys
sys.path.insert(0, 'src')

from app import create_app
app = create_app()
app.app_context().push()

from app.models import ModelCapability

# Test the exact slug used in generation
test_slug = 'openai_codex-mini'
m = ModelCapability.query.filter_by(canonical_slug=test_slug).first()

print(f"Looking for: {test_slug}")
if m:
    print(f"FOUND: canonical_slug={m.canonical_slug}, model_id={m.model_id}")
else:
    print("NOT FOUND")
    print("\nSearching for similar slugs...")
    all_models = ModelCapability.query.filter(
        ModelCapability.canonical_slug.like('%codex%')
    ).all()
    for model in all_models:
        print(f"  - {model.canonical_slug} -> {model.model_id}")
