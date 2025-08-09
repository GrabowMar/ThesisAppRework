"""
Basic frontend integration test without external dependencies.
Tests the new modern UI components and template rendering.
"""

import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from app import create_app
from extensions import get_session
from models import ModelCapability, GeneratedApplication, PortConfiguration


def test_frontend_integration_basic():
    """Integration test that doesn't require Selenium."""
    print("🧪 Testing frontend integration...")
    
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    
    # Setup test data
    with app.app_context():
        with get_session() as session:
            # Create test model capability
            test_model = ModelCapability(
                provider='anthropic',
                model_name='claude-3.7-sonnet',
                model_slug='anthropic_claude-3.7-sonnet',
                supports_code_generation=True,
                supports_web_development=True,
                context_window=200000,
                max_output_tokens=4096,
                cost_per_input_token=0.000015,
                cost_per_output_token=0.000075
            )
            session.merge(test_model)
            
            # Create test application
            test_app = GeneratedApplication(
                model_slug='anthropic_claude-3.7-sonnet',
                app_number=1,
                provider='anthropic',
                status='stopped',
                frontend_port=3001,
                backend_port=5001,
                description='Test web application for integration testing'
            )
            session.merge(test_app)
            
            # Create port configuration
            port_config = PortConfiguration(
                model_slug='anthropic_claude-3.7-sonnet',
                app_number=1,
                frontend_port=3001,
                backend_port=5001,
                allocated=True
            )
            session.merge(port_config)
            
            session.commit()
    
    with app.test_client() as client:
        print("  ✓ Testing dashboard loads...")
        response = client.get('/')
        assert response.status_code == 200
        content = response.data.decode('utf-8')
        assert 'dashboard' in content.lower()
        assert 'AI Model Research Platform' in content
        print("    Dashboard loads successfully with modern UI")
        
        print("  ✓ Testing models page loads...")
        response = client.get('/models')
        assert response.status_code == 200
        content = response.data.decode('utf-8')
        assert 'models-overview' in content.lower()
        assert 'anthropic' in content.lower()
        print("    Models page loads successfully")
        
        print("  ✓ Testing app details page loads...")
        response = client.get('/app/anthropic_claude-3.7-sonnet/1')
        assert response.status_code == 200
        content = response.data.decode('utf-8')
        assert 'app-details' in content.lower()
        assert 'claude-3.7-sonnet' in content
        print("    App details page loads successfully")
        
        print("  ✓ Testing CSS file is accessible...")
        response = client.get('/static/css/modern.css')
        assert response.status_code == 200
        assert 'css' in response.headers.get('content-type', '').lower()
        
        css_content = response.data.decode('utf-8')
        assert '.dashboard' in css_content
        assert '.models-overview' in css_content
        assert '.app-details' in css_content
        assert '--color-primary-500' in css_content  # Check CSS variables
        print("    Modern CSS loads and contains expected classes")
        
        print("  ✓ Testing JavaScript functionality...")
        # Test that pages include modern JS functions
        app_details_response = client.get('/app/anthropic_claude-3.7-sonnet/1')
        app_content = app_details_response.data.decode('utf-8')
        assert 'showNotification' in app_content
        assert 'showLoading' in app_content
        assert 'startApp()' in app_content
        print("    JavaScript functions are properly included")
        
        print("  ✓ Testing template inheritance...")
        # Check that pages extend the base template
        assert 'extends "base.html"' in open('src/templates/pages/dashboard.html').read()
        assert 'extends "base.html"' in open('src/templates/pages/models_overview.html').read()
        assert 'extends "base.html"' in open('src/templates/pages/app_details.html').read()
        print("    Template inheritance is properly configured")
        
        print("  ✓ Testing responsive design classes...")
        # Check for responsive design in CSS
        assert '@media (max-width: 768px)' in css_content
        assert 'grid-template-columns' in css_content
        assert 'flex-direction: column' in css_content
        print("    Responsive design classes are present")


def test_template_rendering():
    """Test that templates render correctly with proper context."""
    print("🎨 Testing template rendering...")
    
    app = create_app()
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        # Test dashboard template variables
        response = client.get('/')
        content = response.data.decode('utf-8')
        
        # Should contain modern UI elements
        assert 'class="dashboard"' in content
        assert 'class="welcome-section"' in content
        assert 'class="stat-card"' in content
        assert 'class="quick-actions"' in content
        print("  ✓ Dashboard template renders with modern UI components")
        
        # Test models overview template
        response = client.get('/models')
        content = response.data.decode('utf-8')
        
        assert 'class="models-overview"' in content
        assert 'class="models-grid"' in content
        print("  ✓ Models overview template renders correctly")


def test_ui_consistency():
    """Test UI consistency across pages."""
    print("🎯 Testing UI consistency...")
    
    app = create_app()
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        pages_to_test = [
            ('/', 'Dashboard'),
            ('/models', 'Models Overview'),
            ('/app/anthropic_claude-3.7-sonnet/1', 'App Details')
        ]
        
        for url, page_name in pages_to_test:
            response = client.get(url)
            content = response.data.decode('utf-8')
            
            # Check for consistent base template elements
            assert '<html lang="en">' in content
            assert 'class="sidebar"' in content
            assert 'class="main-content"' in content
            assert 'Font Awesome' in content or 'fas fa-' in content
            
            print(f"  ✓ {page_name} has consistent base template elements")


def test_modern_features():
    """Test modern UI features and enhancements."""
    print("✨ Testing modern UI features...")
    
    # Check CSS file for modern features
    css_path = 'src/static/css/modern.css'
    with open(css_path, 'r', encoding='utf-8') as f:
        css_content = f.read()
    
    # Check for CSS Grid and Flexbox
    assert 'display: grid' in css_content
    assert 'display: flex' in css_content
    print("  ✓ Modern layout systems (Grid/Flexbox) are used")
    
    # Check for CSS custom properties (variables)
    assert '--color-primary-500' in css_content
    assert '--space-4' in css_content
    assert '--border-radius' in css_content
    print("  ✓ CSS custom properties are defined")
    
    # Check for animations and transitions
    assert 'transition:' in css_content
    assert 'animation:' in css_content
    print("  ✓ Animations and transitions are included")
    
    # Check for hover states
    assert ':hover' in css_content
    print("  ✓ Interactive hover states are defined")


def run_all_tests():
    """Run all frontend integration tests."""
    print("🚀 Starting Frontend Integration Tests")
    print("=" * 50)
    
    try:
        test_frontend_integration_basic()
        print()
        test_template_rendering()
        print()
        test_ui_consistency()
        print()
        test_modern_features()
        
        print()
        print("=" * 50)
        print("✅ All frontend integration tests passed!")
        print("✅ Modern UI refactor is working correctly!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    
    return True


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
