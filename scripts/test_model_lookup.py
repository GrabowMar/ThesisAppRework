"""Test model lookup logic for OpenRouter API calls."""
import sys
sys.path.insert(0, 'c:/Users/grabowmar/Desktop/ThesisAppRework/src')

from app.models import ModelCapability
from app.factory import create_app

app = create_app()
app.app_context().push()

test_slugs = [
    'anthropic_claude-4.5-haiku-20251001',
    'openai_gpt-5-mini-2025-08-07',
    'google_gemini-2.5-flash-preview-09-2025'
]

print('Testing model lookup:\n')
for slug in test_slugs:
    model = ModelCapability.query.filter_by(canonical_slug=slug).first()
    if model:
        print(f'✓ Slug: {slug}')
        print(f'  -> OpenRouter model_id: {model.model_id}')
    else:
        print(f'✗ Slug: {slug}')
        print(f'  -> NOT FOUND IN DATABASE')
    print()
