#!/usr/bin/env python3
"""Test report generation after request context fix"""
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app.factory import create_app

def test_report_generation():
    """Test model analysis report generation"""
    app = create_app()
    
    with app.app_context():
        # Import service directly
        from app.services.report_generation_service import ReportGenerationService
        report_service = ReportGenerationService()
        
        try:
            print("Testing model analysis report generation...")
            report = report_service.generate_report(
                report_type='model_analysis',
                format='html',
                config={'model_slug': 'openai_gpt-4.1-2025-04-14'},
                title='Test Model Analysis Report',
                user_id=1
            )
            
            print(f"✅ Report generated successfully!")
            print(f"   ID: {report.id}")
            print(f"   Type: {report.report_type}")
            print(f"   Format: {report.format}")
            print(f"   Status: {report.status}")
            print(f"   File: {report.file_path}")
            
            # Check file exists
            if os.path.exists(report.file_path):
                file_size = os.path.getsize(report.file_path)
                print(f"   Size: {file_size:,} bytes")
                
                # Read first 500 chars of HTML
                with open(report.file_path, 'r', encoding='utf-8') as f:
                    preview = f.read(500)
                print(f"\n📄 HTML Preview (first 500 chars):\n{preview}...")
            else:
                print(f"   ⚠️ File not found at {report.file_path}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == '__main__':
    test_report_generation()
