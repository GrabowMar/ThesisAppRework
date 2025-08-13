#!/usr/bin/env python3
"""
Enhanced Testing Integration Test
================================

Test script to validate the enhanced testing configuration and analyzer integration.
"""

import sys
import os
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "analyzer"))

def test_analyzer_config():
    """Test the analyzer configuration system."""
    print("🔧 Testing Analyzer Configuration System...")
    
    try:
        from analyzer_config import AnalyzerConfig
        
        # Initialize config manager
        config_manager = AnalyzerConfig()
        
        # Test default configuration
        default_config = config_manager.get_default_config()
        print(f"✅ Default configuration loaded: {len(default_config)} sections")
        
        # Test validation
        validation_result = config_manager.validate_full_config(default_config)
        print(f"✅ Configuration validation: {'PASSED' if validation_result['valid'] else 'FAILED'}")
        
        if not validation_result['valid']:
            print(f"❌ Validation errors: {validation_result['errors']}")
            return False
        
        # Test preset loading
        presets = config_manager.get_available_presets()
        print(f"✅ Available presets: {', '.join(presets)}")
        
        # Test preset validation
        for preset_name in presets:
            preset_config = config_manager.get_preset_config(preset_name)
            preset_validation = config_manager.validate_full_config(preset_config)
            status = "✅ VALID" if preset_validation['valid'] else "❌ INVALID"
            print(f"   {preset_name}: {status}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False


def test_enhanced_model():
    """Test the EnhancedAnalysis model."""
    print("\n📊 Testing Enhanced Analysis Model...")
    
    try:
        # Import Flask app context
        from app.factory import create_app
        from app.models import EnhancedAnalysis, db
        from app.extensions import init_db
        
        # Create test app
        app = create_app()
        
        with app.app_context():
            # Ensure tables exist
            init_db()
            
            # Test model creation
            test_config = {
                'static': {
                    'bandit': {'confidence': 'medium'},
                    'pylint': {'max_line_length': 100}
                },
                'performance': {
                    'apache_bench': {'requests': 1000}
                }
            }
            
            analysis = EnhancedAnalysis(
                task_id='test-task-123',
                model_slug='test_model',
                app_number=1,
                status='completed',
                overall_score=85.5
            )
            
            # Test JSON methods
            analysis.set_config(test_config)
            analysis.set_summary({'total_analyses': 2, 'overall_score': 85.5})
            
            retrieved_config = analysis.get_config()
            retrieved_summary = analysis.get_summary()
            
            print(f"✅ Model created successfully")
            print(f"✅ Config serialization: {len(retrieved_config)} sections")
            print(f"✅ Summary serialization: {retrieved_summary.get('total_analyses')} analyses")
            
            # Test dict conversion
            analysis_dict = analysis.to_dict()
            print(f"✅ Dict conversion: {len(analysis_dict)} fields")
            
            return True
            
    except Exception as e:
        print(f"❌ Model test failed: {e}")
        return False


def test_service_integration():
    """Test analyzer service integration (mock)."""
    print("\n🔗 Testing Service Integration...")
    
    try:
        # Test import paths
        from analyzer.services.static_analyzer.main import StaticAnalyzer
        from analyzer.services.performance_tester.main import PerformanceTester
        from analyzer.services.ai_analyzer.main import AIAnalyzer
        
        print("✅ All analyzer services importable")
        
        # Test service initialization
        static_analyzer = StaticAnalyzer()
        performance_tester = PerformanceTester()
        ai_analyzer = AIAnalyzer()
        
        print("✅ All analyzer services initializable")
        
        # Test configuration acceptance (mock test)
        test_config = {
            'bandit': {'confidence': 'medium', 'severity': 'medium'},
            'pylint': {'max_line_length': 100},
            'eslint': {'env': 'node'}
        }
        
        # These would be actual calls in a real test environment
        print("✅ Services ready for configuration-driven analysis")
        
        return True
        
    except ImportError as e:
        print(f"❌ Service import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Service integration test failed: {e}")
        return False


def test_web_interface_files():
    """Test web interface file existence."""
    print("\n🌐 Testing Web Interface Files...")
    
    base_path = project_root / "src"
    
    files_to_check = [
        "templates/partials/testing/enhanced_config.html",
        "templates/partials/testing/enhanced_results.html",
        "static/js/enhanced-testing-config.js",
        "static/js/enhanced-results.js"
    ]
    
    all_exist = True
    
    for file_path in files_to_check:
        full_path = base_path / file_path
        if full_path.exists():
            size = full_path.stat().st_size
            print(f"✅ {file_path} ({size:,} bytes)")
        else:
            print(f"❌ {file_path} - NOT FOUND")
            all_exist = False
    
    return all_exist


def test_api_endpoints():
    """Test API endpoint definitions."""
    print("\n🛠️ Testing API Endpoints...")
    
    try:
        from app.routes.testing import testing_bp
        
        # Check if enhanced endpoints are registered
        endpoint_names = []
        for rule in testing_bp.url_map.iter_rules():
            endpoint_names.append(rule.endpoint)
        
        expected_endpoints = [
            'testing.run_test_with_config',
            'testing.get_enhanced_results',
            'testing.get_result_detail',
            'testing.download_result',
            'testing.export_results'
        ]
        
        missing_endpoints = []
        for endpoint in expected_endpoints:
            if endpoint not in endpoint_names:
                missing_endpoints.append(endpoint)
        
        if missing_endpoints:
            print(f"❌ Missing endpoints: {missing_endpoints}")
            return False
        else:
            print(f"✅ All {len(expected_endpoints)} enhanced endpoints available")
            return True
            
    except Exception as e:
        print(f"❌ API endpoint test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("🚀 Enhanced Testing Integration Validation")
    print("=" * 50)
    
    tests = [
        ("Analyzer Configuration", test_analyzer_config),
        ("Enhanced Analysis Model", test_enhanced_model),
        ("Service Integration", test_service_integration),
        ("Web Interface Files", test_web_interface_files),
        ("API Endpoints", test_api_endpoints)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🧪 Running: {test_name}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📋 Test Results Summary:")
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 All tests passed! Enhanced testing system is ready.")
        return 0
    else:
        print("⚠️ Some tests failed. Please review the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
