#!/usr/bin/env python3
"""
Quick Test Demonstration Script
==============================

This script demonstrates the analyzer infrastructure testing on real models.
It's a simplified version that runs a quick test to verify everything works.

Usage:
    python quick_test_demo.py
"""

import asyncio
import sys
from pathlib import Path
import logging

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))

from test_real_models import AnalyzerTester, ANALYZER_SERVICES

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


async def quick_demo():
    """Run a quick demonstration of the analyzer testing infrastructure."""
    
    print("🚀 Starting Quick Analyzer Infrastructure Demo")
    print("=" * 60)
    
    # Initialize tester
    tester = AnalyzerTester()
    db_path = Path(__file__).parent.parent / "src" / "data" / "thesis_app.db"
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        print("Make sure you've run the main application first to create the database.")
        return False
    
    try:
        print(f"📊 Connecting to database: {db_path}")
        tester.initialize(str(db_path))
        
        # Get available models
        available_models = tester.get_available_models()
        print(f"📋 Found {len(available_models)} model directories:")
        for model in available_models[:5]:  # Show first 5
            print(f"   • {model}")
        if len(available_models) > 5:
            print(f"   ... and {len(available_models) - 5} more")
        
        # Select a test model (use anthropic_claude-3.7-sonnet as it has most apps)
        test_model = "anthropic_claude-3.7-sonnet"
        if test_model not in available_models:
            test_model = available_models[0] if available_models else None
        
        if not test_model:
            print("❌ No models available for testing")
            return False
        
        print(f"\n🎯 Testing with model: {test_model}")
        
        # Get test applications (limit to first 2 apps for quick demo)
        applications = tester.get_model_applications([test_model], [1, 2], max_apps=2)
        
        if not applications:
            print(f"❌ No applications found for model: {test_model}")
            return False
        
        print(f"📱 Found {len(applications)} applications to test:")
        for app in applications:
            print(f"   • {app.model_name}/app{app.app_number} (ports: {app.frontend_port}/{app.backend_port})")
            print(f"     Backend: {'✓' if app.has_backend else '✗'}, Frontend: {'✓' if app.has_frontend else '✗'}, Docker: {'✓' if app.has_docker_compose else '✗'}")
        
        # Test with static analyzer only for quick demo
        analyzer_types = ['static']
        
        print(f"\n🔍 Testing analyzers: {', '.join(analyzer_types)}")
        print("Note: This demo only tests static analysis. Other analyzers require running services.")
        
        # Check if analyzer services are available
        print("\n📡 Checking analyzer service availability:")
        for analyzer_type in ANALYZER_SERVICES:
            service_config = ANALYZER_SERVICES[analyzer_type]
            print(f"   {service_config['name']}: Port {service_config['port']}")
        
        print("\n⚡ Starting analysis tests...")
        print("(This may take a few minutes depending on code size)")
        
        # Run tests
        results = await tester.test_multiple_applications(applications, analyzer_types, parallel=1)
        
        # Show results
        print("\n✅ Analysis completed! Results:")
        tester.print_summary(results)
        
        # Save a simple report
        report = tester.generate_report(results)
        report_file = tester.save_report(report, "quick_demo_report.json")
        
        print(f"\n📄 Demo report saved: {report_file}")
        
        return True
        
    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        print(f"❌ Demo failed: {e}")
        return False
    
    finally:
        if tester.db_manager:
            tester.db_manager.disconnect()


async def main():
    """Main demo function."""
    print("Analyzer Infrastructure Quick Demo")
    print("This demonstrates testing the analyzer services on real AI-generated models.")
    print()
    
    try:
        success = await quick_demo()
        
        if success:
            print("\n🎉 Demo completed successfully!")
            print("\nNext steps:")
            print("1. Run analyzer services: cd analyzer && python run_all_services.py")
            print("2. Full test: python test_real_models.py --quick")
            print("3. Comprehensive test: python test_real_models.py --all-models")
        else:
            print("\n⚠️ Demo encountered issues. Check the logs above.")
            
    except KeyboardInterrupt:
        print("\n⚠️ Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
