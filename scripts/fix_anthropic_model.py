#!/usr/bin/env python3
"""Quick fix for Anthropic Claude Haiku 4.5 model ID."""

import sys
sys.path.insert(0, 'src')

from app import create_app
from app.models import ModelCapability
from app.extensions import db

app = create_app()

with app.app_context():
    model = ModelCapability.query.filter_by(
        canonical_slug='anthropic_claude-4.5-haiku-20251001'
    ).first()
    
    if model:
        print(f"Found model: {model.canonical_slug}")
        print(f"Current hugging_face_id: '{model.hugging_face_id}'")
        print(f"Current base_model_id: {model.base_model_id}")
        print(f"Current model_id: {model.model_id}")
        
        # The OpenRouter ID is anthropic/claude-haiku-4.5
        # We verified this works in the test
        correct_id = 'anthropic/claude-haiku-4.5'
        
        # Update the field that's being used (hugging_face_id is empty, so base_model_id is used)
        print(f"\n✅ Setting hugging_face_id to: {correct_id}")
        model.hugging_face_id = correct_id
        
        db.session.commit()
        print("✅ Database updated successfully")
        
        # Verify
        model = ModelCapability.query.filter_by(
            canonical_slug='anthropic_claude-4.5-haiku-20251001'
        ).first()
        fallback_id = model.hugging_face_id or model.base_model_id or model.model_id
        print(f"\n✅ Verification - OpenRouter will use: {fallback_id}")
    else:
        print("❌ Model not found")
