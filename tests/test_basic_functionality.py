"""
Simple test to verify basic route functionality without Flask test client issues.
"""
import pytest
from pathlib import Path
import sys
import os

# Add src to path
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

def test_app_can_be_created():
    """Test that we can create the Flask app without errors."""
    try:
        from app import create_app
        app = create_app()
        assert app is not None
        assert hasattr(app, 'config')
        print("✓ App creation works")
    except Exception as e:
        pytest.fail(f"Failed to create app: {e}")

def test_basic_route_registration():
    """Test that routes are properly registered."""
    try:
        from app import create_app
        app = create_app()
        
        # Check if routes are registered
        routes = [rule.rule for rule in app.url_map.iter_rules()]
        assert '/' in routes, "Dashboard route not found"
        print(f"✓ Found {len(routes)} registered routes")
        
        # Print some routes for debugging
        main_routes = [r for r in routes if not r.startswith(('/static', '/api'))]
        print(f"Main routes: {main_routes[:10]}")  # Show first 10
        
    except Exception as e:
        pytest.fail(f"Failed to check routes: {e}")

def test_route_functions_exist():
    """Test that route handler functions exist."""
    try:
        from web_routes import (
            main_bp, api_bp, statistics_bp, batch_bp, docker_bp
        )
        
        # Check blueprints exist
        blueprints = [main_bp, api_bp, statistics_bp, batch_bp, docker_bp]
        
        for bp in blueprints:
            assert bp is not None, f"Blueprint {bp.name} is None"
        
        print(f"✓ All {len(blueprints)} blueprints exist")
        
    except ImportError as e:
        pytest.fail(f"Failed to import blueprints: {e}")

def test_service_helpers_exist():
    """Test that service helper functions exist."""
    try:
        from web_routes import (
            get_settings, get_app_status, get_container_logs,
            get_app_files, get_file_content
        )
        
        # These should be callable functions
        helpers = [get_settings, get_app_status, get_container_logs,
                  get_app_files, get_file_content]
        
        for helper in helpers:
            assert callable(helper), f"Helper {helper.__name__} is not callable"
        
        print(f"✓ All {len(helpers)} service helpers are callable")
        
    except ImportError as e:
        pytest.fail(f"Failed to import service helpers: {e}")

if __name__ == "__main__":
    test_app_can_be_created()
    test_basic_route_registration()
    test_route_functions_exist()
    test_service_helpers_exist()
    print("All basic tests passed!")
