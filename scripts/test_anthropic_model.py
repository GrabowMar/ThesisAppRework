#!/usr/bin/env python3
"""Test Anthropic model validation and generation."""

import sys
import os
sys.path.insert(0, 'src')

from app import create_app
from app.models import ModelCapability

def main():
    app = create_app()
    
    with app.app_context():
        # Check database
        print("=" * 80)
        print("Database Check")
        print("=" * 80)
        
        model = ModelCapability.query.filter_by(
            canonical_slug='anthropic_claude-4.5-haiku-20251001'
        ).first()
        
        if model:
            print(f"✅ Model found in database:")
            print(f"   canonical_slug: {model.canonical_slug}")
            print(f"   hugging_face_id: {model.hugging_face_id}")
            print(f"   model_id: {model.model_id}")
            print(f"   provider: {model.provider}")
        else:
            print(f"❌ Model NOT found in database")
            return
        
        # Check with ModelValidator
        print("\n" + "=" * 80)
        print("ModelValidator Check (OpenRouter Catalog)")
        print("=" * 80)
        
        from app.services.model_validator import ModelValidator
        validator = ModelValidator()
        
        # Try to validate against catalog
        is_valid = validator.is_valid_model_id(model.hugging_face_id)
        print(f"   Model ID: {model.hugging_face_id}")
        print(f"   Valid in OpenRouter: {is_valid}")
        
        if is_valid:
            info = validator.get_model_info(model.hugging_face_id)
            if info:
                print(f"   Name: {info.get('name')}")
                print(f"   Context: {info.get('context_length')} tokens")
        else:
            print(f"   ⚠️  Checking for closest match...")
            closest = validator.find_closest_match(model.hugging_face_id)
            if closest:
                print(f"   💡 Closest match: {closest}")

if __name__ == '__main__':
    main()
