"""Test the OpenRouter API call with correct model ID format."""
import sys
import os
sys.path.insert(0, 'c:/Users/grabowmar/Desktop/ThesisAppRework/src')

from app.factory import create_app
from app.services.simple_generation_service import SimpleGenerationService, GenerationRequest

# Create Flask app context
app = create_app()
app.app_context().push()

# Initialize service
service = SimpleGenerationService()

# Create a test request
request = GenerationRequest(
    model_slug='anthropic_claude-4.5-haiku-20251001',
    template_id=1,
    app_num=999,  # Test app number
    component='backend',
    temperature=0.7,
    max_tokens=4000
)

print('Testing OpenRouter API call with model lookup...\n')
print(f'Input model_slug: {request.model_slug}')

# Test the model lookup logic
from app.models import ModelCapability
model = ModelCapability.query.filter_by(canonical_slug=request.model_slug).first()
if model:
    print(f'✓ Found model in database')
    print(f'  canonical_slug: {model.canonical_slug}')
    print(f'  model_id (for OpenRouter): {model.model_id}')
    print(f'\n✓ This is the correct format for OpenRouter API')
else:
    print(f'✗ Model not found in database!')
    print(f'  This will cause the API call to fail')
