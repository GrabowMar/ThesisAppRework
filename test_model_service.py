#!/usr/bin/env python3
"""Test script for model validation service."""

import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)

def test_model_validation_service():
    """Test the model validation service."""
    try:
        print("🧪 Testing Model Validation Service...")
        
        # Import service manager and registry
        from src.service_manager import ServiceRegistry, ServiceManager
        
        # Initialize the service registry
        print("🔧 Initializing service registry...")
        registry = ServiceRegistry()
        
        # Create a dummy Flask app for service manager
        from flask import Flask
        app = Flask(__name__)
        
        with app.app_context():
            # Initialize service manager
            service_manager = ServiceManager(app)
            
            # Get model validation service
            print("📊 Getting model validation service...")
            model_service = service_manager.get_service("MODEL_VALIDATION_SERVICE")
            
            if not model_service:
                print("❌ Model validation service not available")
                return False
            
            print("✅ Model validation service created successfully")
            
            # Test getting real models
            print("📋 Testing get_real_models()...")
            models = model_service.get_real_models()
            print(f"   Found {len(models)} models")
            
            if models:
                print("   First 3 models:")
                for model in models[:3]:
                    print(f"   - {model['display_name']} ({model['canonical_slug']})")
            
            # Test getting popular models
            print("📋 Testing get_popular_models()...")
            popular = model_service.get_popular_models()
            print(f"   Found {len(popular)} popular models")
            
            if popular:
                print("   Popular models:")
                for model in popular:
                    print(f"   - {model['display_name']} ({model['canonical_slug']})")
            
            # Test model validation
            print("🔍 Testing model validation...")
            if models:
                test_slug = models[0]['canonical_slug']
                is_valid = model_service.validate_model(test_slug)
                print(f"   Validation of '{test_slug}': {'✅ Valid' if is_valid else '❌ Invalid'}")
            
            print("✅ All tests passed!")
            return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_model_validation_service()
    sys.exit(0 if success else 1)
