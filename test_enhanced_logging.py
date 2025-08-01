#!/usr/bin/env python3
"""
Test Enhanced Logging for Security Analysis Service

This script tests the enhanced logging functionality we just added
to the security analysis service without database complications.
"""

import sys
import os
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Set up basic logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler()]
)

def test_backend_security_tools():
    """Test backend security tools availability and logging."""
    print("🔍 Testing Backend Security Tools Logging")
    print("=" * 50)
    
    try:
        from security_analysis_service import BackendSecurityAnalyzer
        
        # Initialize analyzer
        base_path = Path(__file__).parent / "src"
        analyzer = BackendSecurityAnalyzer(base_path)
        
        print(f"📊 Available tools: {list(analyzer.available_tools.keys())}")
        print(f"✅ Tool availability: {analyzer.available_tools}")
        
        # Test the _run_tool method on a simple command to see enhanced logging
        print("\n🧪 Testing enhanced tool execution logging...")
        
        # Test a simple command to see our logging in action
        test_result = analyzer._run_tool("bandit", ["bandit", "--version"], None, working_dir=base_path)
        print(f"📋 Test result: {type(test_result)} with status: {test_result.get('status', 'unknown') if isinstance(test_result, dict) else 'not dict'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Backend test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_frontend_security_tools():
    """Test frontend security tools availability and logging."""
    print("\n🌐 Testing Frontend Security Tools Logging")
    print("=" * 50)
    
    try:
        from security_analysis_service import FrontendSecurityAnalyzer
        
        # Initialize analyzer
        base_path = Path(__file__).parent / "src"
        analyzer = FrontendSecurityAnalyzer(base_path)
        
        print(f"📊 Available tools: {list(analyzer.available_tools.keys())}")
        print(f"✅ Tool availability: {analyzer.available_tools}")
        
        return True
        
    except Exception as e:
        print(f"❌ Frontend test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run enhanced logging tests."""
    print("🧪 Testing Enhanced Security Analysis Logging")
    print("=" * 60)
    
    backend_success = test_backend_security_tools()
    frontend_success = test_frontend_security_tools()
    
    print("\n" + "=" * 60)
    if backend_success and frontend_success:
        print("✅ All enhanced logging tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
