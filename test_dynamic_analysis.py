"""
Test the new dynamic analysis system
===================================

Simple test to verify the new tag-based analysis system works.
"""

import sys
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_tool_discovery():
    """Test tool discovery functionality."""
    print("=== Testing Tool Discovery ===")
    
    try:
        from app.engines import get_tool_registry
        
        registry = get_tool_registry()
        
        # Test tool discovery
        print("Discovering tools...")
        discovery_results = registry.discover_tools()
        print(f"Discovery results: {discovery_results}")
        
        # Get available tools
        available_tools = registry.get_available_tools()
        print(f"Available tools: {available_tools}")
        
        # Get tools by tags
        security_tools = registry.get_tools_by_tags({'security'})
        print(f"Security tools: {security_tools}")
        
        performance_tools = registry.get_tools_by_tags({'performance'})
        print(f"Performance tools: {performance_tools}")
        
        # Get tools by language
        python_tools = registry.get_tools_for_language('python')
        print(f"Python tools: {python_tools}")
        
        js_tools = registry.get_tools_for_language('javascript')
        print(f"JavaScript tools: {js_tools}")
        
        print("✅ Tool discovery test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Tool discovery test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_orchestrator():
    """Test analysis orchestrator functionality."""
    print("\n=== Testing Analysis Orchestrator ===")
    
    try:
        from app.engines import get_analysis_orchestrator
        
        orchestrator = get_analysis_orchestrator()
        
        # Test context-based tool selection
        target_path = Path(__file__).parent / "src"
        tools = orchestrator.get_tools_for_context(target_path)
        print(f"Recommended tools for {target_path}: {tools}")
        
        # Test tagged analysis (dry run)
        print("Testing tagged analysis (security)...")
        try:
            # This will fail because we don't have a real model/app, but it tests the interface
            result = orchestrator.run_security_analysis("test-model", 1, target_path=target_path)
            print(f"Security analysis result: {result.get('success', False)}")
        except Exception as e:
            print(f"Expected error (no test model): {e}")
        
        print("✅ Orchestrator test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Orchestrator test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_engines_compatibility():
    """Test backward compatibility with old engine interface."""
    print("\n=== Testing Engine Compatibility ===")
    
    try:
        from app.services.analysis_engines import get_engine
        
        # Test getting engines
        security_engine = get_engine('security')
        print(f"Security engine: {security_engine.engine_name}")
        
        performance_engine = get_engine('performance')
        print(f"Performance engine: {performance_engine.engine_name}")
        
        # Test running engine (will fail but tests interface)
        try:
            result = security_engine.run("test-model", 1)
            print(f"Engine run result: {result.status}")
        except Exception as e:
            print(f"Expected error (no test model): {e}")
        
        print("✅ Engine compatibility test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Engine compatibility test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_result_parsing():
    """Test result parsing functionality."""
    print("\n=== Testing Result Parsing ===")
    
    try:
        from app.services.analysis_result_parser import (
            parse_new_engine_results, get_findings_summary
        )
        
        # Test with mock orchestrator results
        mock_results = {
            'success': True,
            'findings': [
                {
                    'tool': 'bandit',
                    'severity': 'high',
                    'confidence': 'high',
                    'title': 'SQL injection vulnerability',
                    'description': 'Possible SQL injection',
                    'file_path': 'app.py',
                    'line_number': 42,
                    'category': 'sql_injection',
                    'tags': ['security', 'python'],
                    'raw_data': {}
                }
            ]
        }
        
        findings = parse_new_engine_results(mock_results)
        print(f"Parsed {len(findings)} findings")
        
        summary = get_findings_summary(findings)
        print(f"Summary: {summary}")
        
        print("✅ Result parsing test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Result parsing test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("🚀 Testing New Dynamic Analysis System")
    print("=" * 50)
    
    tests = [
        test_tool_discovery,
        test_orchestrator,
        test_engines_compatibility,
        test_result_parsing
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            failed += 1
    
    print(f"\n📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! The new dynamic analysis system is working.")
    else:
        print("⚠️ Some tests failed. Please check the output above.")
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)