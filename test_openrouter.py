#!/usr/bin/env python3
"""
Test script to verify OpenRouter API integration
"""
import os
import sys
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

def test_api_key():
    """Test if API key is accessible"""
    api_key = os.getenv('OPENROUTER_API_KEY')
    if api_key:
        print(f"✅ OPENROUTER_API_KEY found (length: {len(api_key)})")
        print(f"   Key prefix: {api_key[:15]}...")
        return api_key
    else:
        print("❌ OPENROUTER_API_KEY not found")
        return None

def test_api_connectivity(api_key):
    """Test basic connectivity to OpenRouter API"""
    if not api_key:
        return False
    
    print("\n🔗 Testing OpenRouter API connectivity...")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://thesis-app.local",
        "X-Title": "Thesis Research App",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            models = data.get("data", [])
            print(f"✅ API connectivity successful!")
            print(f"   Found {len(models)} models")
            if models:
                sample_models = [m.get('id', 'unknown') for m in models[:3]]
                print(f"   Sample models: {sample_models}")
            return True
        else:
            print(f"❌ API error: {response.status_code} - {response.text[:200]}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Connection error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_openrouter_service():
    """Test the integrated OpenRouter service"""
    print("\n🔧 Testing OpenRouterService integration...")
    
    try:
        from app.services.openrouter_service import OpenRouterService
        
        service = OpenRouterService()
        
        if not service.api_key:
            print("❌ Service doesn't have API key")
            return False
        
        print("✅ OpenRouterService initialized successfully")
        
        # Test model fetching
        print("   Fetching models from service...")
        models = service.fetch_all_models()
        
        if models:
            print(f"✅ Service fetched {len(models)} models")
            # Show sample model
            if models:
                sample = models[0]
                print(f"   Sample model: {sample.get('id', 'unknown')} - {sample.get('name', 'no name')[:50]}")
            return True
        else:
            print("❌ Service returned no models")
            return False
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Service error: {e}")
        return False

if __name__ == "__main__":
    print("🧪 OpenRouter Integration Test")
    print("=" * 40)
    
    # Test 1: API Key
    api_key = test_api_key()
    
    # Test 2: Direct API connectivity  
    if api_key:
        api_works = test_api_connectivity(api_key)
    else:
        api_works = False
    
    # Test 3: Service integration
    if api_works:
        service_works = test_openrouter_service()
    else:
        service_works = False
    
    print("\n" + "=" * 40)
    if api_key and api_works and service_works:
        print("🎉 All OpenRouter tests passed!")
    else:
        print("⚠️  Some OpenRouter tests failed")
        if not api_key:
            print("   - API key not configured")
        if not api_works:
            print("   - API connectivity failed")
        if not service_works:
            print("   - Service integration failed")