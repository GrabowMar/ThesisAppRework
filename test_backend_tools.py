#!/usr/bin/env python3
"""
Test script to verify backend security tools are detected
"""

import sys
from pathlib import Path

# Add src to path to import security_analysis_service
sys.path.insert(0, str(Path(__file__).parent / "src"))

from security_analysis_service import UnifiedCLIAnalyzer, ToolCategory

def test_backend_tools():
    """Test if backend security tools are detected."""
    base_path = Path(__file__).parent
    analyzer = UnifiedCLIAnalyzer(base_path)
    
    print("=== Backend Security Tools Detection Test ===")
    
    # Check backend security tools
    backend_analyzer = analyzer.analyzers[ToolCategory.BACKEND_SECURITY]
    print(f"\nBackend Security Tools Available:")
    for tool_name, is_available in backend_analyzer.available_tools.items():
        status = "✅ Available" if is_available else "❌ Not Available"
        print(f"  {tool_name}: {status}")
    
    # Check all tools
    print(f"\nAll Available Tools by Category:")
    available_tools = analyzer.get_available_tools()
    for category, tools in available_tools.items():
        print(f"  {category}: {tools}")
    
    return backend_analyzer.available_tools

if __name__ == "__main__":
    available_tools = test_backend_tools()
    
    # Summary
    available_count = sum(1 for is_available in available_tools.values() if is_available)
    total_count = len(available_tools)
    
    print(f"\n=== Summary ===")
    print(f"Available: {available_count}/{total_count} backend security tools")
    
    if available_count > 0:
        print("✅ SUCCESS: Backend security tools are now working!")
    else:
        print("❌ FAILURE: No backend security tools detected")
