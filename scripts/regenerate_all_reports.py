#!/usr/bin/env python3
"""Regenerate all existing reports with corrected metrics.

This script backfills all completed reports that may contain stale/incorrect
data due to the findings-count truncation bug (findings list capped at 50 per app).

Usage:
    cd ThesisAppRework
    python3 regenerate_all_reports.py
"""

import sys
import json
from pathlib import Path

# Set up path so we can import from src/
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

from app.factory import create_app
from app.extensions import db
from app.models import Report
from app.services.service_locator import ServiceLocator


def main() -> int:
    app = create_app("development")

    with app.app_context():
        report_service = ServiceLocator.get_report_service()
        if not report_service:
            print("ERROR: ReportService not available")
            return 1

        # Get all completed reports
        reports = Report.query.filter(Report.status == 'completed').order_by(Report.created_at).all()
        print(f"Found {len(reports)} completed reports to regenerate\n")

        if not reports:
            print("No reports to regenerate.")
            return 0

        success_count = 0
        fail_count = 0

        for report in reports:
            report_id = report.report_id
            report_type = report.report_type
            title = report.title or "(untitled)"

            # Capture before-state for comparison
            old_data = report.get_report_data()
            old_total = None
            if old_data and isinstance(old_data, dict):
                summary = old_data.get('summary', {})
                old_total = summary.get('total_findings')

            print(f"--- Regenerating: [{report_type}] {title} (id={report_id})")

            try:
                result = report_service.regenerate_report(report_id)
                if result and result.status == 'completed':
                    new_data = result.get_report_data()
                    new_total = None
                    if new_data and isinstance(new_data, dict):
                        new_summary = new_data.get('summary', {})
                        new_total = new_summary.get('total_findings')

                    delta = ""
                    if old_total is not None and new_total is not None:
                        diff = new_total - old_total
                        if diff != 0:
                            delta = f"  (delta: {'+' if diff > 0 else ''}{diff})"
                        else:
                            delta = "  (unchanged)"

                    findings_info = ""
                    if new_total is not None:
                        findings_info = f" | total_findings: {old_total} -> {new_total}{delta}"

                    print(f"  OK{findings_info}")
                    success_count += 1
                else:
                    status = result.status if result else 'None'
                    err = result.error_message if result else 'no result returned'
                    print(f"  FAILED: status={status}, error={err}")
                    fail_count += 1

            except Exception as e:
                print(f"  EXCEPTION: {e}")
                fail_count += 1

        print(f"\n{'='*60}")
        print(f"Done: {success_count} succeeded, {fail_count} failed out of {len(reports)} total")
        return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
