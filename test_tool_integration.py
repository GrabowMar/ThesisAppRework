#!/usr/bin/env python3
"""
Test script to verify complete integration of dynamic tools with the UI system.
Tests both dynamic tool discovery and API endpoint integration.
"""
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_dynamic_tool_registry():
    """Test dynamic tool discovery"""
    print("=== Testing Dynamic Tool Registry ===")
    
    try:
        from app.engines.base import get_tool_registry
        registry = get_tool_registry()
        
        # Ensure all engines are imported (same as ToolRegistryService does)
        import app.engines.backend_security  # noqa: F401
        import app.engines.frontend_security  # noqa: F401
        import app.engines.performance  # noqa: F401
        
        # Get tool names and info
        tool_names = registry.get_available_tools()
        all_tools_info = registry.get_all_tools_info()
        
        print(f"Available tools (with executables): {len(tool_names)}")
        print(f"All registered tools: {len(all_tools_info)}")
        
        print("\nAll registered tools:")
        for name, info in all_tools_info.items():
            available = name in tool_names
            print(f"  - {name}: {info.get('description', 'No description')[:50]}...")
            print(f"    Tags: {', '.join(info.get('tags', []))}")
            print(f"    Category: {info.get('category', 'unknown')}")
            print(f"    Available: {available}")
            print()
        
        return len(all_tools_info) > 0
    except Exception as e:
        print(f"Error testing dynamic registry: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_endpoint_integration():
    """Test API endpoint integration with Flask app"""
    print("=== Testing API Endpoint Integration ===")
    
    try:
        from app.factory import create_app
        app = create_app()
        
        with app.app_context():
            from app.services.service_locator import ServiceLocator
            tool_service = ServiceLocator.get_tool_registry_service()
            
            if not tool_service:
                print("❌ ToolRegistryService not found in ServiceLocator")
                return False
            
            print("✅ ToolRegistryService found in ServiceLocator")
            
            # Test get_all_tools method
            all_tools = tool_service.get_all_tools(enabled_only=False)  # Show all tools, not just available
            print(f"Total tools from service: {len(all_tools)}")
            
            # Count by source
            db_tools = [t for t in all_tools if t.get('source') == 'database']
            dynamic_tools = [t for t in all_tools if t.get('source') == 'dynamic']
            
            print(f"  - Database tools: {len(db_tools)}")
            print(f"  - Dynamic tools: {len(dynamic_tools)}")
            
            # Test category filtering
            categories = tool_service.get_tools_by_category('security')
            print(f"Security category tools: {len(categories)}")
            
            # Show some dynamic tools
            if dynamic_tools:
                print("\nDynamic tools details:")
                for tool in dynamic_tools[:3]:  # Show first 3
                    print(f"  - {tool.get('name')}: {tool.get('description', 'No description')[:50]}...")
                    print(f"    Category: {tool.get('category')}")
                    print(f"    Tags: {tool.get('tags', [])}")
                    print(f"    Available: {tool.get('is_enabled', 'unknown')}")
            
            # Also test with enabled_only=True to see the difference
            enabled_tools = tool_service.get_all_tools(enabled_only=True)
            print(f"\nEnabled-only tools: {len(enabled_tools)}")
            
            return len(dynamic_tools) > 0
            
    except Exception as e:
        print(f"Error testing API integration: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_http_endpoint():
    """Test actual HTTP endpoint"""
    print("=== Testing HTTP Endpoint ===")
    
    try:
        from app.factory import create_app
        app = create_app()
        
        with app.test_client() as client:
            response = client.get('/api/tool-registry/tools')
            
            if response.status_code != 200:
                print(f"❌ HTTP endpoint failed: {response.status_code}")
                return False
            
            data = response.get_json()
            if not data:
                print("❌ No JSON data returned")
                return False
            
            # Check if it's the expected format with 'data' field
            tools = data.get('data', [])
            if not tools:
                # Fallback to check 'tools' field
                tools = data.get('tools', [])
            
            print(f"✅ HTTP endpoint returned {len(tools)} tools")
            
            # Count by source
            dynamic_tools = [t for t in tools if t.get('source') == 'dynamic']
            print(f"  - Dynamic tools via HTTP: {len(dynamic_tools)}")
            
            if dynamic_tools:
                print("\nSample dynamic tool from HTTP:")
                tool = dynamic_tools[0]
                print(f"  Name: {tool.get('name')}")
                print(f"  Description: {tool.get('description', 'No description')[:50]}...")
                print(f"  Category: {tool.get('category')}")
                print(f"  Source: {tool.get('source')}")
            else:
                print("\nAll tools from HTTP:")
                for i, tool in enumerate(tools[:3]):  # Show first 3
                    print(f"  {i+1}. {tool.get('name')}: {tool.get('category')} (source: {tool.get('source', 'unknown')})")
            
            return len(tools) > 0
    
    except Exception as e:
        print(f"Error testing HTTP endpoint: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("Testing Dynamic Tool Integration with UI System")
    print("=" * 50)
    
    results = []
    
    # Test 1: Dynamic tool registry
    results.append(test_dynamic_tool_registry())
    print()
    
    # Test 2: Service integration
    results.append(test_api_endpoint_integration())
    print()
    
    # Test 3: HTTP endpoint
    results.append(test_http_endpoint())
    print()
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print("=" * 50)
    print(f"SUMMARY: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All tests passed! Dynamic tools should be visible in UI.")
    else:
        print("❌ Some tests failed. Check the output above for details.")
    
    return passed == total

if __name__ == "__main__":
    sys.exit(0 if main() else 1)