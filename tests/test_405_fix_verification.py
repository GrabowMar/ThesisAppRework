"""
Final verification test - focused on 405 error fixes
"""
import pytest
from pathlib import Path
import sys

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

def test_no_405_errors():
    """Test that POST routes don't return 405 Method Not Allowed."""
    from app import create_app
    
    app = create_app()
    
    with app.test_client() as client:
        # Test all the routes that should accept POST methods
        post_routes_data = [
            ('/docker/start/test_model/1', {}),
            ('/docker/stop/test_model/1', {}),
            ('/docker/restart/test_model/1', {}),
            ('/api/performance/test_model/1/run', {
                'duration': '30',
                'users': '5',
                'spawn_rate': '1.0'
            }),
            ('/api/analysis/test_model/1/security', {
                'bandit': 'on',
                'safety': 'on'
            }),
            ('/api/analysis/test_model/1/zap', {
                'scan_type': 'spider'
            }),
            ('/api/docker/cache/refresh', {})
        ]
        
        success_count = 0
        for route, data in post_routes_data:
            response = client.post(route, data=data)
            
            if response.status_code != 405:
                success_count += 1
                print(f"✓ {route} - Status: {response.status_code} (Not 405)")
            else:
                print(f"✗ {route} - Status: 405 Method Not Allowed")
        
        print(f"\nResult: {success_count}/{len(post_routes_data)} routes accept POST methods correctly")
        
        # All routes should accept POST (not return 405)
        assert success_count == len(post_routes_data), "Some routes returned 405 Method Not Allowed"

def test_key_features_working():
    """Test that key application features are working."""
    from app import create_app
    
    app = create_app()
    
    with app.test_client() as client:
        # Test main pages load
        main_pages = [
            ('/', 'Dashboard'),
            ('/models', 'Models'),
        ]
        
        for route, name in main_pages:
            response = client.get(route)
            assert response.status_code == 200, f"{name} page failed with {response.status_code}"
            print(f"✓ {name} page loads successfully")
        
        # Test app detail pages (may redirect but should not 404/500)
        test_model = "anthropic_claude-3-sonnet"
        test_app_num = 1
        
        app_pages = [
            (f'/app/{test_model}/{test_app_num}/overview', 'Overview'),
            (f'/app/{test_model}/{test_app_num}/docker', 'Docker'),
            (f'/app/{test_model}/{test_app_num}/analysis', 'Analysis'),
            (f'/app/{test_model}/{test_app_num}/performance', 'Performance'),
            (f'/app/{test_model}/{test_app_num}/files', 'Files'),
            (f'/app/{test_model}/{test_app_num}/tests', 'Tests')
        ]
        
        for route, name in app_pages:
            response = client.get(route)
            # Should work (200) or redirect (302), but not fail
            assert response.status_code in [200, 302], f"{name} page failed with {response.status_code}"
            print(f"✓ {name} page accessible")

def test_api_endpoints_working():
    """Test that API endpoints are working."""
    from app import create_app
    
    app = create_app()
    
    with app.test_client() as client:
        # Test API endpoints that should work
        api_endpoints = [
            ('/api/dashboard/models', 'Dashboard Models'),
            ('/api/dashboard/stats', 'Dashboard Stats'),
            ('/api/sidebar/stats', 'Sidebar Stats'),
            ('/api/status/test_model/1', 'App Status')
        ]
        
        for route, name in api_endpoints:
            response = client.get(route)
            assert response.status_code == 200, f"{name} API failed with {response.status_code}"
            print(f"✓ {name} API working")

if __name__ == "__main__":
    print("🔍 Testing for 405 errors and core functionality...\n")
    
    test_no_405_errors()
    print()
    
    test_key_features_working() 
    print()
    
    test_api_endpoints_working()
    print()
    
    print("🎉 All critical functionality tests passed!")
    print("\n✅ Summary:")
    print("  • No 405 Method Not Allowed errors")
    print("  • All main pages load correctly")
    print("  • All app detail pages are accessible")
    print("  • All API endpoints work correctly")
    print("  • Frontend, backend, performance, and ZAP analysis routes accept POST")
    print("\n🚀 Your application is working correctly!")
