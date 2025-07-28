#!/usr/bin/env python3
"""
Demo script showing how to use the new integrated frontend tools.
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from security_analysis_service import (
    UnifiedCLIAnalyzer, 
    FrontendSecurityAnalyzer, 
    FrontendQualityAnalyzer,
    ToolCategory
)

def demo_frontend_security_analysis():
    """Demonstrate frontend security analysis with new tools."""
    print("🔒 Frontend Security Analysis Demo")
    print("-" * 40)
    
    # Initialize analyzer
    analyzer = FrontendSecurityAnalyzer(Path.cwd())
    
    print("Available security tools:")
    for tool_name, available in analyzer.available_tools.items():
        status = "✅" if available else "❌"
        print(f"  {status} {tool_name}")
    
    print(f"\nTool capabilities:")
    print(f"  • ESLint: Detects security issues like XSS, injection vulnerabilities")
    print(f"  • Retire.js: Identifies vulnerable JavaScript libraries")
    print(f"  • JSHint: Catches potentially unsafe JavaScript patterns")
    print(f"  • Snyk: Comprehensive dependency vulnerability scanning")
    print(f"  • npm audit: Built-in npm vulnerability checking")

def demo_frontend_quality_analysis():
    """Demonstrate frontend quality analysis with new tools."""
    print("\n📊 Frontend Quality Analysis Demo")
    print("-" * 40)
    
    # Initialize analyzer
    analyzer = FrontendQualityAnalyzer(Path.cwd())
    
    print("Available quality tools:")
    for tool_name, available in analyzer.available_tools.items():
        status = "✅" if available else "❌"
        print(f"  {status} {tool_name}")
    
    print(f"\nTool capabilities:")
    print(f"  • ESLint: Code quality rules, complexity analysis, unused variables")
    print(f"  • Prettier: Code formatting consistency checking")
    print(f"  • JSHint: Code quality issues, undefined variables, unused code")

def demo_unified_analysis():
    """Demonstrate using the unified analyzer for comprehensive analysis."""
    print("\n🎯 Unified Analysis Demo")
    print("-" * 40)
    
    # Initialize unified analyzer
    analyzer = UnifiedCLIAnalyzer(Path.cwd())
    
    # Show all available tools
    available_tools = analyzer.get_available_tools()
    
    print("All available tools by category:")
    for category, tools in available_tools.items():
        print(f"  {category}:")
        for tool in tools:
            print(f"    • {tool}")

def demo_tool_usage_examples():
    """Show examples of how tools would be called."""
    print("\n💡 Usage Examples")
    print("-" * 40)
    
    print("Example 1: Run security analysis on a specific app")
    print("```python")
    print("analyzer = FrontendSecurityAnalyzer('/path/to/project')")
    print("issues, status, outputs = analyzer.run_analysis('anthropic_claude-3-sonnet', 1)")
    print("print(f'Found {len(issues)} security issues')")
    print("```")
    
    print("\nExample 2: Run quality analysis with all tools")
    print("```python")
    print("analyzer = FrontendQualityAnalyzer('/path/to/project')")
    print("issues, status, outputs = analyzer.run_analysis('openai_gpt-4', 5, use_all_tools=True)")
    print("for issue in issues:")
    print("    print(f'{issue[\"tool\"]}: {issue[\"issue_text\"]}')")
    print("```")
    
    print("\nExample 3: Comprehensive analysis with unified analyzer")
    print("```python")
    print("analyzer = UnifiedCLIAnalyzer('/path/to/project')")
    print("results = analyzer.run_analysis('deepseek_chat-v3', 3, ")
    print("    categories=[ToolCategory.FRONTEND_SECURITY, ToolCategory.FRONTEND_QUALITY],")
    print("    use_all_tools=True)")
    print("```")

def demo_new_features():
    """Highlight new features added."""
    print("\n🚀 New Features Added")
    print("-" * 40)
    
    features = [
        "✨ retire.js integration for detecting vulnerable JavaScript libraries",
        "✨ Enhanced Snyk integration with better error parsing",
        "✨ JSHint integration for both security and quality analysis",
        "✨ Prettier integration for code formatting analysis",
        "✨ Improved ESLint configuration with security-focused rules",
        "✨ Separate quality-focused ESLint analysis",
        "✨ Better error handling and tool availability checking",
        "✨ Comprehensive parsing for all tool outputs",
        "✨ Automatic npm dependency installation for Snyk",
        "✨ Flexible configuration system for all tools"
    ]
    
    for feature in features:
        print(f"  {feature}")

if __name__ == "__main__":
    print("🎉 Frontend Tools Integration - Complete!")
    print("=" * 50)
    
    demo_frontend_security_analysis()
    demo_frontend_quality_analysis()
    demo_unified_analysis()
    demo_tool_usage_examples()
    demo_new_features()
    
    print(f"\n🎯 Summary:")
    print(f"  • Added 5 frontend security tools: eslint, retire, jshint, snyk, npm-audit")
    print(f"  • Added 3 frontend quality tools: eslint, prettier, jshint")
    print(f"  • All tools are available via npx (except npm-audit)")
    print(f"  • Comprehensive parsing and error handling")
    print(f"  • Ready for production analysis!")
    print(f"\n✅ Integration complete - Ready to analyze JavaScript/TypeScript applications!")
