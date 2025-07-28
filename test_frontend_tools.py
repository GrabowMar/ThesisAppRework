#!/usr/bin/env python3
"""
Test script for frontend security and quality analysis tools integration.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

try:
    from security_analysis_service import (
        UnifiedCLIAnalyzer, 
        FrontendSecurityAnalyzer, 
        FrontendQualityAnalyzer,
        ToolCategory
    )
    print("✅ Successfully imported analysis modules")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

def test_available_tools():
    """Test that tools are detected correctly."""
    print("\n=== Testing Available Tools ===")
    
    # Test unified analyzer
    analyzer = UnifiedCLIAnalyzer(Path.cwd())
    available_tools = analyzer.get_available_tools()
    
    print("Available tools by category:")
    for category, tools in available_tools.items():
        print(f"  {category}: {tools}")
    
    # Test frontend security analyzer
    print("\n--- Frontend Security Tools ---")
    frontend_security = FrontendSecurityAnalyzer(Path.cwd())
    print(f"Available frontend security tools: {list(frontend_security.available_tools.keys())}")
    
    # Test frontend quality analyzer
    print("\n--- Frontend Quality Tools ---")
    frontend_quality = FrontendQualityAnalyzer(Path.cwd())
    print(f"Available frontend quality tools: {list(frontend_quality.available_tools.keys())}")

def test_tool_definitions():
    """Test tool definitions are properly configured."""
    print("\n=== Testing Tool Definitions ===")
    
    frontend_security = FrontendSecurityAnalyzer(Path.cwd())
    frontend_quality = FrontendQualityAnalyzer(Path.cwd())
    
    print("Frontend Security Tool Definitions:")
    for tool_name, config in frontend_security.tools.items():
        print(f"  {tool_name}: {config}")
    
    print("\nFrontend Quality Tool Definitions:")
    for tool_name, config in frontend_quality.tools.items():
        print(f"  {tool_name}: {config}")

if __name__ == "__main__":
    print("🧪 Testing Frontend Tools Integration")
    print("=" * 50)
    
    try:
        test_available_tools()
        test_tool_definitions()
        print("\n✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
