#!/usr/bin/env python3
"""Comprehensive report system verification"""
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app.factory import create_app
from app.services.report_generation_service import ReportGenerationService

def test_all_report_types():
    """Test all three report types"""
    app = create_app()
    
    with app.app_context():
        service = ReportGenerationService()
        results = []
        
        # Test 1: Model Analysis Report
        print("=" * 60)
        print("TEST 1: Model Analysis Report")
        print("=" * 60)
        try:
            report = service.generate_report(
                report_type='model_analysis',
                format='html',
                config={'model_slug': 'anthropic_claude-4.5-haiku-20251001'},
                title='Model Analysis - Claude Haiku 4.5',
                user_id=1
            )
            print(f"✅ Model Analysis Report Generated")
            print(f"   ID: {report.id}")
            print(f"   File: {report.file_path}")
            # Resolve full path
            full_path = Path(service.reports_dir) / report.file_path
            if full_path.exists():
                print(f"   Size: {full_path.stat().st_size:,} bytes")
                results.append(('model_analysis', True, str(full_path)))
            else:
                print(f"   ⚠️ File not found at {full_path}")
                results.append(('model_analysis', False, f"File not found: {full_path}"))
        except Exception as e:
            print(f"❌ Failed: {e}")
            results.append(('model_analysis', False, str(e)))
        
        # Test 2: App Analysis Report (comparison)
        print("\n" + "=" * 60)
        print("TEST 2: App Comparison Report")
        print("=" * 60)
        try:
            report = service.generate_report(
                report_type='app_analysis',
                format='html',
                config={
                    'model_slug': 'anthropic_claude-4.5-haiku-20251001',
                    'app_number': 1  # Single app analysis
                },
                title='App Analysis - App 1',
                user_id=1
            )
            print(f"✅ App Comparison Report Generated")
            print(f"   ID: {report.id}")
            print(f"   File: {report.file_path}")
            # Resolve full path
            full_path = Path(service.reports_dir) / report.file_path
            if full_path.exists():
                print(f"   Size: {full_path.stat().st_size:,} bytes")
                results.append(('app_analysis', True, str(full_path)))
            else:
                print(f"   ⚠️ File not found at {full_path}")
                results.append(('app_analysis', False, f"File not found: {full_path}"))
        except Exception as e:
            print(f"❌ Failed: {e}")
            results.append(('app_analysis', False, str(e)))
        
        # Test 3: Tool Analysis Report
        print("\n" + "=" * 60)
        print("TEST 3: Tool Performance Report")
        print("=" * 60)
        try:
            report = service.generate_report(
                report_type='tool_analysis',
                format='html',
                config={'tool_name': 'eslint'},
                title='Tool Analysis - ESLint',
                user_id=1
            )
            print(f"✅ Tool Analysis Report Generated")
            print(f"   ID: {report.id}")
            print(f"   File: {report.file_path}")
            # Resolve full path
            full_path = Path(service.reports_dir) / report.file_path
            if full_path.exists():
                print(f"   Size: {full_path.stat().st_size:,} bytes")
                results.append(('tool_analysis', True, str(full_path)))
            else:
                print(f"   ⚠️ File not found at {full_path}")
                results.append(('tool_analysis', False, f"File not found: {full_path}"))
        except Exception as e:
            print(f"❌ Failed: {e}")
            results.append(('tool_analysis', False, str(e)))
        
        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        successes = [r for r in results if r[1]]
        failures = [r for r in results if not r[1]]
        
        print(f"✅ Passed: {len(successes)}/3")
        print(f"❌ Failed: {len(failures)}/3")
        
        if successes:
            print("\nGenerated Reports:")
            for report_type, _, path in successes:
                print(f"  • {report_type}: {path}")
        
        if failures:
            print("\nFailed Reports:")
            for report_type, _, error in failures:
                print(f"  • {report_type}: {error[:100]}...")
        
        return len(failures) == 0

if __name__ == '__main__':
    success = test_all_report_types()
    sys.exit(0 if success else 1)
