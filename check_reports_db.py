#!/usr/bin/env python3
"""Verify database records for generated reports"""
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app.factory import create_app
from app.models import Report

def check_reports_db():
    """Check recent report records in database"""
    app = create_app()
    
    with app.app_context():
        # Get last 10 reports
        reports = Report.query.order_by(Report.created_at.desc()).limit(10).all()
        
        print("=" * 70)
        print("RECENT REPORTS IN DATABASE")
        print("=" * 70)
        
        if not reports:
            print("No reports found in database.")
            return False
        
        # Group by status
        by_status = {}
        for r in reports:
            by_status.setdefault(r.status, []).append(r)
        
        print(f"\nTotal Reports: {len(reports)}")
        print(f"Status Breakdown: {', '.join(f'{k}: {len(v)}' for k, v in by_status.items())}")
        
        print("\n" + "-" * 70)
        print(f"{'ID':<5} {'Type':<20} {'Format':<8} {'Status':<12} {'Created':<20}")
        print("-" * 70)
        
        for r in reports:
            created = r.created_at.strftime('%Y-%m-%d %H:%M:%S') if r.created_at else 'N/A'
            print(f"{r.id:<5} {r.report_type:<20} {r.format:<8} {r.status:<12} {created:<20}")
        
        # Show details of latest completed report
        completed = [r for r in reports if r.status == 'completed']
        if completed:
            latest = completed[0]
            print("\n" + "=" * 70)
            print("LATEST COMPLETED REPORT DETAILS")
            print("=" * 70)
            print(f"ID: {latest.id}")
            print(f"Type: {latest.report_type}")
            print(f"Title: {latest.title or '(No title)'}")
            print(f"Description: {latest.description or '(No description)'}")
            print(f"Format: {latest.format}")
            print(f"File: {latest.file_path}")
            print(f"Status: {latest.status}")
            print(f"Created: {latest.created_at}")
            print(f"Expires: {latest.expires_at or 'Never'}")
            
            # Check file exists
            from pathlib import Path
            from app.services.report_generation_service import ReportGenerationService
            
            service = ReportGenerationService()
            full_path = Path(service.reports_dir) / latest.file_path
            
            if full_path.exists():
                size = full_path.stat().st_size
                print(f"\n✅ File exists: {full_path}")
                print(f"   Size: {size:,} bytes ({size/1024:.1f} KB)")
            else:
                print(f"\n⚠️ File not found: {full_path}")
        
        return True

if __name__ == '__main__':
    success = check_reports_db()
    sys.exit(0 if success else 1)
