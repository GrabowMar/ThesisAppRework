#!/usr/bin/env python3
"""Test script to verify analysis pipeline fixes."""
import sys
import os
import json
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from app.factory import create_app
from app.services.analyzer_manager_wrapper import AnalyzerManagerWrapper

def test_single_analysis():
    """Run a single analysis to test the fixes."""
    app = create_app()
    with app.app_context():
        print("=" * 80)
        print("Testing Analysis Pipeline Fixes")
        print("=" * 80)

        # Test with an existing generated app
        model_slug = "google_gemini-3-flash-preview-20251217"
        app_number = 1
        task_name = f"test_fix_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        print(f"\nRunning comprehensive analysis:")
        print(f"  Model: {model_slug}")
        print(f"  App: {app_number}")
        print(f"  Task: {task_name}")
        print()

        try:
            wrapper = AnalyzerManagerWrapper()
            result = wrapper.run_comprehensive_analysis(
                model_slug=model_slug,
                app_number=app_number,
                task_name=task_name,
                tools=None  # Run all tools
            )

            print("\n" + "=" * 80)
            print("ANALYSIS RESULTS")
            print("=" * 80)

            # Extract summary
            results = result.get('results', {})
            summary = results.get('summary', {})
            services = results.get('services', {})

            print(f"\nStatus: {summary.get('status', 'unknown')}")
            print(f"Services Executed: {summary.get('services_executed', 0)}")
            print(f"Tools Executed: {summary.get('tools_executed', 0)}")
            print(f"Total Findings: {summary.get('total_findings', 0)}")

            print("\nService Status:")
            for service_name, service_data in services.items():
                status = service_data.get('status', 'unknown')
                error = service_data.get('error', '')
                print(f"  {service_name}: {status}")
                if error and 'cannot schedule new futures' in str(error):
                    print(f"    ❌ ERROR: {error}")
                elif error:
                    print(f"    ⚠️  ERROR: {error}")
                elif status == 'success':
                    print(f"    ✓ Success")

            # Check for the critical error
            has_event_loop_error = False
            for service_name, service_data in services.items():
                error = str(service_data.get('error', ''))
                if 'cannot schedule new futures' in error or 'interpreter shutdown' in error:
                    has_event_loop_error = True
                    print(f"\n❌ CRITICAL: Event loop error detected in {service_name}")
                    break

            if not has_event_loop_error:
                print("\n✅ SUCCESS: No event loop errors detected!")
                print("The fixes are working correctly.")
            else:
                print("\n❌ FAILURE: Event loop errors still present.")
                print("Additional debugging required.")

            return not has_event_loop_error

        except Exception as e:
            print(f"\n❌ Exception during analysis: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = test_single_analysis()
    sys.exit(0 if success else 1)
