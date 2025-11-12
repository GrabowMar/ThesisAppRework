"""
Simple test to verify report file creation
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from app.factory import create_app
from app.services.service_locator import ServiceLocator

app = create_app()

with app.app_context():
    service_locator = ServiceLocator()
    report_service = service_locator.get_report_service()
    
    print(f"Reports directory: {report_service.reports_dir}")
    print(f"Exists: {report_service.reports_dir.exists()}")
    
    # Generate a simple JSON report
    config = {
        "period_days": 30,
        "include_trends": True,
        "include_recommendations": True,
        "model_slugs": ["anthropic_claude-4.5-haiku-20251001"]
    }
    
    report = report_service.generate_report(
        report_type="executive_summary",
        format="json",
        config=config,
        title="Test Report",
        description="Simple test",
        user_id=None,
        expires_in_days=30
    )
    
    print(f"\nReport generated:")
    print(f"  ID: {report.report_id}")
    print(f"  Status: {report.status}")
    print(f"  File path (relative): {report.file_path}")
    print(f"  File size: {report.file_size} bytes")
    
    if report.file_path:
        full_path = report_service.reports_dir / report.file_path
        print(f"  Full path: {full_path}")
        print(f"  File exists: {full_path.exists()}")
        
        if full_path.exists():
            print(f"  Actual size: {full_path.stat().st_size} bytes")
        else:
            print(f"  ERROR: File not found at {full_path}")
            
            # Check parent directory
            parent = full_path.parent
            print(f"\n  Parent dir: {parent}")
            print(f"  Parent exists: {parent.exists()}")
            if parent.exists():
                print(f"  Files in parent: {list(parent.iterdir())}")
