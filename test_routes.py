#!/usr/bin/env python3
"""
Simple Test for New Routes Implementation
==========================================

Test the new batch and statistics routes without starting the web server.
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_batch_and_statistics_implementation():
    """Test that the new batch and statistics implementation works."""
    print("🧪 Testing Batch Testing and Statistics Implementation")
    print("=" * 60)
    
    try:
        # Test imports
        print("1. Testing imports...")
        from app.routes.batch import batch_bp
        from app.routes.statistics import stats_bp
        from app.factory import create_app
        print("   ✅ All imports successful")
        
        # Test app creation
        print("\n2. Testing app creation...")
        app = create_app()
        
        # Check blueprints
        blueprint_names = [bp.name for bp in app.blueprints.values()]
        print(f"   📝 Registered blueprints: {blueprint_names}")
        
        if 'batch' in blueprint_names:
            print("   ✅ Batch blueprint registered")
        else:
            print("   ❌ Batch blueprint missing")
            return False
            
        if 'statistics' in blueprint_names:
            print("   ✅ Statistics blueprint registered")
        else:
            print("   ❌ Statistics blueprint missing")
            return False
        
        # Test URL generation
        print("\n3. Testing URL generation...")
        with app.app_context():
            try:
                batch_url = app.url_for('batch.batch_overview')
                stats_url = app.url_for('statistics.statistics_overview')
                print(f"   ✅ Batch URL: {batch_url}")
                print(f"   ✅ Statistics URL: {stats_url}")
            except Exception as e:
                print(f"   ❌ URL generation failed: {e}")
                return False
        
        # Test database connectivity
        print("\n4. Testing database connectivity...")
        from app.models import ModelCapability, BatchAnalysis
        with app.app_context():
            try:
                model_count = ModelCapability.query.count()
                batch_count = BatchAnalysis.query.count()
                print(f"   ✅ Database connection successful")
                print(f"   📊 {model_count} models, {batch_count} batches in database")
            except Exception as e:
                print(f"   ❌ Database test failed: {e}")
                return False
        
        print("\n" + "=" * 60)
        print("🎉 All tests passed! Implementation is working correctly.")
        print("\n📝 Next steps:")
        print("   1. Start the app: python src/main.py")
        print("   2. Visit http://localhost:5000/batch for batch testing")
        print("   3. Visit http://localhost:5000/statistics for statistics dashboard")
        print("   4. Use navigation menu to access new features")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        print("\n🔧 Troubleshooting tips:")
        print("   - Ensure all dependencies are installed")
        print("   - Check that the database file exists")
        print("   - Verify that all import paths are correct")
        return False

if __name__ == "__main__":
    success = test_batch_and_statistics_implementation()
    sys.exit(0 if success else 1)
