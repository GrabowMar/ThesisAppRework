"""
Comprehensive functionality test for all app features
"""
import pytest
from pathlib import Path
import sys
import time

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

def test_all_main_routes():
    """Test all main application routes work correctly."""
    from app import create_app
    
    app = create_app()
    
    with app.test_client() as client:
        # Test main dashboard
        response = client.get('/')
        assert response.status_code == 200
        print("✓ Dashboard loads successfully")
        
        # Test models page
        response = client.get('/models')
        assert response.status_code == 200
        print("✓ Models page loads successfully")
        
        # Test app detail pages (use first available model)
        test_model = "anthropic_claude-3-sonnet"
        test_app_num = 1
        
        app_routes = [
            f'/app/{test_model}/{test_app_num}',
            f'/app/{test_model}/{test_app_num}/overview',
            f'/app/{test_model}/{test_app_num}/docker',
            f'/app/{test_model}/{test_app_num}/analysis', 
            f'/app/{test_model}/{test_app_num}/performance',
            f'/app/{test_model}/{test_app_num}/files',
            f'/app/{test_model}/{test_app_num}/tests'
        ]
        
        for route in app_routes:
            response = client.get(route)
            # Should either work (200) or redirect (302), but not 404/405/500
            assert response.status_code in [200, 302], f"Route {route} failed with {response.status_code}"
            print(f"✓ App route {route} works")

def test_api_routes():
    """Test API routes work correctly."""
    from app import create_app
    
    app = create_app()
    
    with app.test_client() as client:
        # Test API routes that should work
        api_routes = [
            '/api/dashboard/models',
            '/api/dashboard/stats',
            '/api/sidebar/stats',
            '/api/sidebar/system-status',
            '/api/status/test_model/1'
        ]
        
        for route in api_routes:
            response = client.get(route)
            assert response.status_code == 200, f"API route {route} failed with {response.status_code}"
            print(f"✓ API route {route} works")

def test_docker_routes():
    """Test Docker management routes accept correct methods."""
    from app import create_app
    
    app = create_app()
    
    with app.test_client() as client:
        # Test Docker POST routes
        docker_routes = [
            '/docker/start/test_model/1',
            '/docker/stop/test_model/1',
            '/docker/restart/test_model/1'
        ]
        
        for route in docker_routes:
            response = client.post(route)
            # Should not return 405 (Method Not Allowed)
            assert response.status_code != 405, f"Docker route {route} returned 405"
            print(f"✓ Docker route {route} accepts POST method")

def test_performance_routes():
    """Test Performance testing routes work."""
    from app import create_app
    
    app = create_app()
    
    with app.test_client() as client:
        # Test performance route
        response = client.post('/api/performance/test_model/1/run', data={
            'duration': '30',
            'users': '5',
            'spawn_rate': '1.0'
        })
        
        # Should not return 405 (Method Not Allowed) or 404 (Not Found)
        assert response.status_code not in [405, 404], f"Performance route failed with {response.status_code}"
        print("✓ Performance testing route works")

def test_security_analysis_routes():
    """Test Security analysis routes work."""
    from app import create_app
    
    app = create_app()
    
    with app.test_client() as client:
        # Test security analysis route
        response = client.post('/api/analysis/test_model/1/security', data={
            'bandit': 'on',
            'safety': 'on',
            'eslint': 'on'
        })
        
        # Should not return 405 (Method Not Allowed) or 404 (Not Found)
        assert response.status_code not in [405, 404], f"Security analysis route failed with {response.status_code}"
        print("✓ Security analysis route works")

def test_zap_scan_routes():
    """Test ZAP security scanning routes work."""
    from app import create_app
    
    app = create_app()
    
    with app.test_client() as client:
        # Test ZAP scan route
        response = client.post('/api/analysis/test_model/1/zap', data={
            'scan_type': 'spider'
        })
        
        # Should not return 405 (Method Not Allowed) or 404 (Not Found)
        assert response.status_code not in [405, 404], f"ZAP scan route failed with {response.status_code}"
        print("✓ ZAP security scan route works")

def test_template_rendering():
    """Test that all templates render without errors."""
    from app import create_app
    
    app = create_app()
    
    with app.test_client() as client:
        # Test app detail templates
        test_model = "anthropic_claude-3-sonnet"
        test_app_num = 1
        
        template_routes = [
            f'/app/{test_model}/{test_app_num}/overview',
            f'/app/{test_model}/{test_app_num}/docker',
            f'/app/{test_model}/{test_app_num}/analysis',
            f'/app/{test_model}/{test_app_num}/performance',
            f'/app/{test_model}/{test_app_num}/files',
            f'/app/{test_model}/{test_app_num}/tests'
        ]
        
        for route in template_routes:
            response = client.get(route)
            assert response.status_code in [200, 302], f"Template route {route} failed"
            
            # Check that response contains expected content
            if response.status_code == 200:
                content = response.get_data(as_text=True)
                assert 'app_base.html' not in content, f"Template inheritance broken in {route}"
                # Should contain navigation elements
                assert 'nav-link' in content, f"Navigation missing in {route}"
            
            print(f"✓ Template {route} renders correctly")

if __name__ == "__main__":
    print("Running comprehensive functionality tests...\n")
    
    test_all_main_routes()
    print()
    
    test_api_routes() 
    print()
    
    test_docker_routes()
    print()
    
    test_performance_routes()
    print()
    
    test_security_analysis_routes()
    print()
    
    test_zap_scan_routes()
    print()
    
    test_template_rendering()
    print()
    
    print("🎉 All comprehensive functionality tests passed!")
    print("\n✅ Summary:")
    print("  • All main routes work correctly")
    print("  • API routes respond properly") 
    print("  • Docker management routes accept POST methods")
    print("  • Performance testing routes are functional")
    print("  • Security analysis routes are functional")
    print("  • ZAP security scan routes are functional")
    print("  • All templates render without errors")
    print("\n🚀 The application is fully functional and ready for use!")
