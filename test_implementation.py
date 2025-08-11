#!/usr/bin/env python3
"""
Test Script for Batch Testing and Statistics Implementation
===========================================================

Simple test script to verify that the new batch testing and statistics
modules are working correctly.
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_imports():
    """Test that all new modules can be imported correctly."""
    print("Testing imports...")
    
    try:
        from app.routes.batch import batch_bp
        print("✅ Batch routes imported successfully")
    except Exception as e:
        print(f"❌ Failed to import batch routes: {e}")
        return False
    
    try:
        from app.routes.statistics import stats_bp
        print("✅ Statistics routes imported successfully")
    except Exception as e:
        print(f"❌ Failed to import statistics routes: {e}")
        return False
    
    try:
        from app.factory import create_app
        print("✅ App factory imported successfully")
    except Exception as e:
        print(f"❌ Failed to import app factory: {e}")
        return False
    
    return True


def test_app_creation():
    """Test that the Flask app can be created with new routes."""
    print("\nTesting app creation...")
    
    try:
        from app.factory import create_app
        app = create_app()
        print("✅ Flask app created successfully")
        
        # Test that blueprints are registered
        blueprint_names = [bp.name for bp in app.blueprints.values()]
        print(f"📝 Registered blueprints: {blueprint_names}")
        
        if 'batch' in blueprint_names:
            print("✅ Batch blueprint registered")
        else:
            print("❌ Batch blueprint not found")
            return False
            
        if 'statistics' in blueprint_names:
            print("✅ Statistics blueprint registered")
        else:
            print("❌ Statistics blueprint not found")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to create app: {e}")
        return False


def test_database_models():
    """Test that database models work correctly."""
    print("\nTesting database models...")
    
    try:
        from app.factory import create_app
        from app.models import ModelCapability, BatchAnalysis, GeneratedApplication
        
        app = create_app()
        
        with app.app_context():
            # Test that we can query models
            model_count = ModelCapability.query.count()
            batch_count = BatchAnalysis.query.count()
            app_count = GeneratedApplication.query.count()
            
            print(f"✅ Database connection successful")
            print(f"📊 Current data: {model_count} models, {batch_count} batches, {app_count} apps")
            
        return True
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False


def test_route_urls():
    """Test that route URLs can be generated."""
    print("\nTesting route URLs...")
    
    try:
        from app.factory import create_app
        
        app = create_app()
        
        with app.app_context():
            # Test batch routes
            batch_urls = {
                'batch_overview': app.url_for('batch.batch_overview'),
                'create_batch': app.url_for('batch.create_batch'),
            }
            print("✅ Batch route URLs generated:")
            for name, url in batch_urls.items():
                print(f"   {name}: {url}")
            
            # Test statistics routes
            stats_urls = {
                'statistics_overview': app.url_for('statistics.statistics_overview'),
                'models_distribution': app.url_for('statistics.api_models_distribution'),
            }
            print("✅ Statistics route URLs generated:")
            for name, url in stats_urls.items():
                print(f"   {name}: {url}")
        
        return True
        
    except Exception as e:
        print(f"❌ Route URL test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("🧪 Testing Batch Testing and Statistics Implementation")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_app_creation,
        test_database_models,
        test_route_urls,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()  # Add spacing between tests
    
    print("=" * 60)
    print(f"🏁 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The implementation is ready.")
        print("\n📝 Next steps:")
        print("   1. Run the app: python src/main.py")
        print("   2. Navigate to /batch for batch testing")
        print("   3. Navigate to /statistics for statistics dashboard")
        return True
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
