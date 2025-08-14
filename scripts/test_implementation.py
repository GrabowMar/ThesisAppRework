#!/usr/bin/env python3
"""
Test Script for Batch Testing and Statistics Implementation
===========================================================

Simple test script to verify that the new batch testing and statistics
modules are working correctly.
"""

import sys
import os

# Add src directory to path (scripts/.. /src)
SRC_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'src'))
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

def test_imports():
    """Test that all new modules can be imported correctly."""
    print("Testing imports...")

    from app.routes.batch import batch_bp  # noqa: F401
    from app.routes.statistics import stats_bp  # noqa: F401
    from app.factory import create_app  # noqa: F401
    # If imports fail, pytest will raise; reaching here means success.


def test_app_creation():
    """Test that the Flask app can be created with new routes."""
    print("\nTesting app creation...")
    from app.factory import create_app
    app = create_app()
    blueprint_names = [bp.name for bp in app.blueprints.values()]
    print(f"📝 Registered blueprints: {blueprint_names}")
    assert 'batch' in blueprint_names, "Batch blueprint not found"
    assert 'statistics' in blueprint_names, "Statistics blueprint not found"


def test_database_models():
    """Test that database models work correctly."""
    print("\nTesting database models...")
    from app.factory import create_app
    from app.models import ModelCapability, BatchAnalysis, GeneratedApplication
    app = create_app()
    with app.app_context():
        model_count = ModelCapability.query.count()
        batch_count = BatchAnalysis.query.count()
        app_count = GeneratedApplication.query.count()
        print(f"📊 Current data: {model_count} models, {batch_count} batches, {app_count} apps")
        # Basic sanity: counts are >= 0
        assert model_count >= 0
        assert batch_count >= 0
        assert app_count >= 0


def test_route_urls():
    """Test that route URLs can be generated."""
    print("\nTesting route URLs...")
    from app.factory import create_app
    app = create_app()
    # Use a request context for URL building
    with app.test_request_context('/'):
        batch_urls = {
            'batch_overview': app.url_for('batch.batch_overview'),
            'create_batch': app.url_for('batch.create_batch'),
        }
        print("✅ Batch route URLs generated:")
        for name, url in batch_urls.items():
            print(f"   {name}: {url}")

        stats_urls = {
            'statistics_overview': app.url_for('statistics.statistics_overview'),
            # API endpoint is registered under the 'api' blueprint
            'models_distribution': app.url_for('api.api_models_distribution'),
        }
        print("✅ Statistics route URLs generated:")
        for name, url in stats_urls.items():
            print(f"   {name}: {url}")
        # Assert URLs are non-empty strings
        for url in list(batch_urls.values()) + list(stats_urls.values()):
            assert isinstance(url, str) and url.startswith('/'), f"Unexpected URL: {url}"


# Retain the standalone runner support

def main():
    """Run all tests manually (outside pytest)."""
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
        try:
            test()
            passed += 1
        except Exception as exc:  # pragma: no cover - manual runner diagnostics
            print(f"❌ {test.__name__} failed: {exc}")
        print()

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


if __name__ == "__main__":  # pragma: no cover
    success = main()
    sys.exit(0 if success else 1)
