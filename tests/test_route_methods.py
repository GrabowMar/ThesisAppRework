"""
Test specific routes that might be causing 405 errors
"""
import pytest
from pathlib import Path
import sys
import os

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

def test_docker_routes():
    """Test docker-related routes that accept POST methods."""
    from app import create_app
    
    app = create_app()
    
    with app.test_client() as client:
        # Test routes that should accept POST
        post_routes = [
            '/docker/start/test_model/1',
            '/docker/stop/test_model/1', 
            '/docker/restart/test_model/1',
            '/api/performance/test_model/1/run',
            '/api/analysis/test_model/1/security',
            '/api/analysis/test_model/1/zap'
        ]
        
        for route in post_routes:
            # Test that the route accepts POST (should not return 405)
            response = client.post(route)
            print(f"Route {route}: Status {response.status_code}")
            
            # 405 means method not allowed - this is what we want to avoid
            assert response.status_code != 405, f"Route {route} returned 405 Method Not Allowed"
            
            # We expect other error codes (like 500 for missing services) but not 405

def test_get_routes():
    """Test GET routes work correctly."""
    from app import create_app
    
    app = create_app()
    
    with app.test_client() as client:
        # Test basic GET routes
        get_routes = [
            '/',
            '/models',
            '/api/status/test_model/1'
        ]
        
        for route in get_routes:
            response = client.get(route)
            print(f"GET Route {route}: Status {response.status_code}")
            
            # These should work (200) or redirect (302), but not 405 or 404
            assert response.status_code not in [404, 405], f"Route {route} returned {response.status_code}"

if __name__ == "__main__":
    test_docker_routes()
    test_get_routes()
    print("All route tests passed!")
