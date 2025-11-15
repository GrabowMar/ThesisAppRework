#!/usr/bin/env python3
"""Test model validation and OpenRouter communication for fixed models."""

import sys
import os
sys.path.insert(0, 'src')

from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.models import ModelCapability
from app.services.model_validator import ModelValidator

def test_model(canonical_slug):
    """Test a specific model's validation and OpenRouter readiness."""
    print(f"\n{'='*80}")
    print(f"Testing: {canonical_slug}")
    print(f"{'='*80}\n")
    
    app = create_app()
    
    with app.app_context():
        # 1. Check database
        model = ModelCapability.query.filter_by(canonical_slug=canonical_slug).first()
        
        if not model:
            print(f"❌ Model NOT found in database")
            return False
        
        print(f"✅ Model found in database:")
        print(f"   canonical_slug: {model.canonical_slug}")
        print(f"   hugging_face_id: '{model.hugging_face_id}'")
        print(f"   model_id: {model.model_id}")
        print(f"   provider: {model.provider}")
        
        # 2. Determine which ID would be used for API calls
        openrouter_id = model.hugging_face_id or model.base_model_id or model.model_id
        print(f"\n📡 OpenRouter API will use: {openrouter_id}")
        
        # 3. Validate against OpenRouter catalog
        validator = ModelValidator()
        is_valid = validator.is_valid_model_id(openrouter_id)
        
        print(f"\n🔍 Validation against OpenRouter catalog:")
        print(f"   Model ID: {openrouter_id}")
        print(f"   Valid: {'✅ YES' if is_valid else '❌ NO'}")
        
        if is_valid:
            info = validator.get_model_info(openrouter_id)
            if info:
                print(f"\n📋 Model Info from OpenRouter:")
                print(f"   Name: {info.get('name')}")
                print(f"   Context Length: {info.get('context_length', 'N/A'):,} tokens")
                modality = info.get('architecture', {}).get('modality', 'N/A')
                print(f"   Modality: {modality}")
                pricing = info.get('pricing', {})
                if pricing:
                    prompt_price = float(pricing.get('prompt', 0)) * 1_000_000
                    completion_price = float(pricing.get('completion', 0)) * 1_000_000
                    print(f"   Pricing: ${prompt_price:.2f}/1M prompt, ${completion_price:.2f}/1M completion")
        else:
            print(f"\n⚠️  Model not found in OpenRouter catalog")
            closest = validator.find_closest_match(openrouter_id)
            if closest:
                print(f"   💡 Closest match: {closest}")
        
        print(f"\n{'='*80}")
        return is_valid

def main():
    print("=" * 80)
    print("Model Validation & OpenRouter Communication Test")
    print("=" * 80)
    
    # Test originally failing model
    test_models = [
        'anthropic_claude-4.5-haiku-20251001',
        'deepseek_deepseek-r1',
        'openai_gpt-4',
        'minimax_minimax-01',
    ]
    
    results = {}
    for model_slug in test_models:
        results[model_slug] = test_model(model_slug)
    
    # Summary
    print(f"\n{'='*80}")
    print("Summary")
    print(f"{'='*80}\n")
    
    total = len(results)
    valid = sum(1 for v in results.values() if v)
    
    print(f"Tested: {total} models")
    print(f"✅ Valid: {valid}")
    print(f"❌ Invalid: {total - valid}")
    
    print("\nDetailed Results:")
    for slug, is_valid in results.items():
        status = "✅ READY" if is_valid else "❌ FAILED"
        print(f"  {status}: {slug}")
    
    if valid == total:
        print(f"\n🎉 All tested models are valid and ready for OpenRouter API calls!")
        return 0
    else:
        print(f"\n⚠️  {total - valid} model(s) failed validation")
        return 1

if __name__ == '__main__':
    sys.exit(main())
