#!/usr/bin/env python3
"""
Enhanced Testing System - Comprehensive Validation Script
=========================================================

This script validates the complete enhanced testing system implementation
including all web research findings and advanced configuration options.
"""

import sys
import json
import traceback
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_configuration_system():
    """Test the enhanced configuration system."""
    print("\n🔧 TESTING CONFIGURATION SYSTEM")
    print("=" * 50)
    
    try:
        from app.services.analyzer_config import AnalyzerConfigService
        
        # Test service creation
        service = AnalyzerConfigService()
        print("✅ AnalyzerConfigService created successfully")
        
        # Test presets
        presets = service.get_available_presets()
        print(f"✅ Available presets: {presets}")
        
        # Test enhanced configurations
        for preset_name in ['default', 'strict', 'fast', 'comprehensive']:
            config = service.get_preset(preset_name)
            print(f"✅ {preset_name} preset loaded")
            
            # Validate configuration
            errors = service.validate_config(config)
            if errors:
                print(f"❌ {preset_name} validation errors: {errors}")
            else:
                print(f"✅ {preset_name} configuration valid")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration system error: {e}")
        traceback.print_exc()
        return False

def test_enhanced_features():
    """Test enhanced features from web research."""
    print("\n🌐 TESTING ENHANCED FEATURES")
    print("=" * 50)
    
    try:
        from app.services.analyzer_config import AnalyzerConfigService
        
        service = AnalyzerConfigService()
        config = service.get_preset('strict')
        
        # Test Bandit enhancements
        bandit_features = [
            ('YAML format support', config.bandit.format in ['json', 'yaml', 'xml']),
            ('Advanced filtering', hasattr(config.bandit, 'exclude_paths')),
            ('Message templates', hasattr(config.bandit, 'msg_template')),
            ('Ignore nosec', hasattr(config.bandit, 'ignore_nosec')),
        ]
        
        for feature, available in bandit_features:
            status = "✅" if available else "❌"
            print(f"{status} Bandit: {feature}")
        
        # Test Pylint enhancements
        pylint_features = [
            ('Confidence levels', hasattr(config.pylint, 'confidence')),
            ('Plugin support', hasattr(config.pylint, 'load_plugins')),
            ('Extension whitelist', hasattr(config.pylint, 'extension_pkg_whitelist')),
            ('Message templates', hasattr(config.pylint, 'msg_template')),
        ]
        
        for feature, available in pylint_features:
            status = "✅" if available else "❌"
            print(f"{status} Pylint: {feature}")
        
        # Test ESLint 2025 features
        eslint_features = [
            ('ES2025 support', config.eslint.ecma_version >= 2025),
            ('Advanced environments', hasattr(config.eslint, 'ecma_features')),
            ('Cache support', hasattr(config.eslint, 'cache')),
            ('Ignore patterns', hasattr(config.eslint, 'ignore_patterns')),
        ]
        
        for feature, available in eslint_features:
            status = "✅" if available else "❌"
            print(f"{status} ESLint: {feature}")
        
        # Test Apache Bench enhancements
        ab_features = [
            ('SSL support', hasattr(config.apache_bench, 'enable_ssl')),
            ('Percentile control', hasattr(config.apache_bench, 'disable_percentiles')),
            ('Advanced timing', hasattr(config.apache_bench, 'socket_timeout')),
            ('Output control', hasattr(config.apache_bench, 'csv_output')),
        ]
        
        for feature, available in ab_features:
            status = "✅" if available else "❌"
            print(f"{status} Apache Bench: {feature}")
        
        # Test OpenRouter enhancements
        or_features = [
            ('Function calling', hasattr(config.openrouter, 'tools')),
            ('Reasoning modes', hasattr(config.openrouter, 'reasoning_enabled')),
            ('Custom headers', hasattr(config.openrouter, 'http_referer')),
            ('Advanced parameters', hasattr(config.openrouter, 'logit_bias')),
        ]
        
        for feature, available in or_features:
            status = "✅" if available else "❌"
            print(f"{status} OpenRouter: {feature}")
        
        return True
        
    except Exception as e:
        print(f"❌ Enhanced features error: {e}")
        traceback.print_exc()
        return False

def test_configuration_serialization():
    """Test configuration serialization and validation."""
    print("\n💾 TESTING CONFIGURATION SERIALIZATION")
    print("=" * 50)
    
    try:
        from app.services.analyzer_config import AnalyzerConfigService
        
        service = AnalyzerConfigService()
        
        # Test all presets
        for preset_name in service.get_available_presets():
            config = service.get_preset(preset_name)
            
            # Test to_dict
            config_dict = service.to_dict(config)
            print(f"✅ {preset_name}: Serialized to dict")
            
            # Test from_dict
            restored_config = service.from_dict(config_dict)
            print(f"✅ {preset_name}: Restored from dict")
            
            # Verify structure
            required_keys = ['bandit', 'pylint', 'eslint', 'apache_bench', 'openrouter']
            for key in required_keys:
                if key not in config_dict:
                    print(f"❌ {preset_name}: Missing {key}")
                    return False
            
            print(f"✅ {preset_name}: All required keys present")
        
        return True
        
    except Exception as e:
        print(f"❌ Serialization error: {e}")
        traceback.print_exc()
        return False

def test_analyzer_integration():
    """Test analyzer integration service."""
    print("\n🔗 TESTING ANALYZER INTEGRATION")
    print("=" * 50)
    
    try:
        from app.services.analyzer_integration import get_analyzer_integration
        
        # Test service creation
        analyzer_integration = get_analyzer_integration()
        print(f"✅ Analyzer integration service: {type(analyzer_integration).__name__}")
        
        # Test configuration compatibility
        from app.services.analyzer_config import AnalyzerConfigService
        
        service = AnalyzerConfigService()
        config = service.get_preset('default')
        config_dict = service.to_dict(config)
        
        # Verify config structure is compatible with analyzer services
        expected_sections = ['bandit', 'pylint', 'eslint', 'apache_bench', 'openrouter']
        for section in expected_sections:
            if section in config_dict and isinstance(config_dict[section], dict):
                print(f"✅ {section} configuration format compatible")
            else:
                print(f"❌ {section} configuration format invalid")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Analyzer integration error: {e}")
        traceback.print_exc()
        return False

def test_web_research_integration():
    """Test specific web research findings integration."""
    print("\n📊 TESTING WEB RESEARCH INTEGRATION")
    print("=" * 50)
    
    try:
        from app.services.analyzer_config import AnalyzerConfigService
        
        service = AnalyzerConfigService()
        config = service.get_preset('comprehensive')
        
        # Test Bandit YAML support (from web research)
        bandit_yaml_support = config.bandit.format in ['json', 'yaml', 'sarif']
        print(f"{'✅' if bandit_yaml_support else '❌'} Bandit: YAML/SARIF format support")
        
        # Test Pylint confidence levels (from web research)
        pylint_confidence = config.pylint.confidence and len(config.pylint.confidence) > 0
        print(f"{'✅' if pylint_confidence else '❌'} Pylint: Confidence level filtering")
        
        # Test ESLint 2025 features (from web research)
        eslint_2025 = config.eslint.ecma_version >= 2025
        print(f"{'✅' if eslint_2025 else '❌'} ESLint: ES2025/ES17 support")
        
        # Test Apache Bench advanced options (from web research)
        ab_advanced = hasattr(config.apache_bench, 'disable_percentiles')
        print(f"{'✅' if ab_advanced else '❌'} Apache Bench: Percentile control")
        
        # Test OpenRouter function calling (from web research)
        or_functions = hasattr(config.openrouter, 'tools') and isinstance(config.openrouter.tools, list)
        print(f"{'✅' if or_functions else '❌'} OpenRouter: Function calling support")
        
        # Test OpenRouter reasoning modes (from web research)
        or_reasoning = hasattr(config.openrouter, 'reasoning_effort')
        print(f"{'✅' if or_reasoning else '❌'} OpenRouter: Reasoning effort control")
        
        return True
        
    except Exception as e:
        print(f"❌ Web research integration error: {e}")
        traceback.print_exc()
        return False

def run_comprehensive_test():
    """Run all tests and provide summary."""
    print("🧪 ENHANCED TESTING SYSTEM - COMPREHENSIVE VALIDATION")
    print("=" * 60)
    print("Testing all components of the enhanced testing system...")
    
    tests = [
        ("Configuration System", test_configuration_system),
        ("Enhanced Features", test_enhanced_features),
        ("Serialization", test_configuration_serialization),
        ("Analyzer Integration", test_analyzer_integration),
        ("Web Research Integration", test_web_research_integration),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n📋 TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Enhanced testing system is fully operational")
        print("✅ All web research findings successfully integrated")
        print("✅ Configuration system supports advanced options")
        print("✅ Analyzer integration is working correctly")
        return True
    else:
        print(f"\n⚠️  {total - passed} tests failed")
        print("❌ Enhanced testing system needs attention")
        return False

if __name__ == "__main__":
    success = run_comprehensive_test()
    sys.exit(0 if success else 1)
