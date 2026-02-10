#!/usr/bin/env python3
"""One-time DB fix: Re-evaluate tasks incorrectly marked FAILED due to
'offset-naive and offset-aware datetimes' error.

For each affected main task:
  - Check subtask statuses
  - If all subtasks completed → set COMPLETED
  - If mixed → set PARTIAL_SUCCESS
  - Clear error_message
  - Recompute actual_duration with tz-safe subtraction

Usage:
    cd /home/ubuntu/ThesisAppRework
    python scripts/fix_datetime_failed_tasks.py          # dry-run (default)
    python scripts/fix_datetime_failed_tasks.py --apply   # actually write changes
"""
import sys
import os

# Add src to path so we can import the app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from datetime import datetime, timezone


def main():
    apply = '--apply' in sys.argv

    from app.factory import create_app
    from app.extensions import db

    app = create_app()
    with app.app_context():
        from app.models.analysis_models import AnalysisTask
        from app.constants import AnalysisStatus

        # Find main tasks with the datetime error
        affected = (
            AnalysisTask.query
            .filter(
                AnalysisTask.is_main_task == True,  # noqa: E712
                AnalysisTask.status == AnalysisStatus.FAILED,
                AnalysisTask.error_message.like('%offset-naive%offset-aware%')
            )
            .all()
        )

        if not affected:
            print("No affected tasks found. Nothing to fix.")
            return

        print(f"Found {len(affected)} affected main task(s):\n")

        for task in affected:
            subtasks = (
                AnalysisTask.query
                .filter(AnalysisTask.parent_task_id == task.task_id)
                .all()
            )

            sub_statuses = [s.status for s in subtasks]
            completed_count = sum(1 for s in sub_statuses if s == AnalysisStatus.COMPLETED)
            failed_count = sum(1 for s in sub_statuses if s == AnalysisStatus.FAILED)
            total = len(subtasks)

            # Determine correct status
            if total == 0:
                # No subtasks — keep as failed (shouldn't happen)
                new_status = AnalysisStatus.FAILED
            elif failed_count == 0:
                new_status = AnalysisStatus.COMPLETED
            elif completed_count == 0:
                new_status = AnalysisStatus.FAILED
            else:
                new_status = AnalysisStatus.PARTIAL_SUCCESS

            # Compute duration safely
            duration = None
            if task.started_at:
                started_at = task.started_at
                if started_at.tzinfo is None:
                    started_at = started_at.replace(tzinfo=timezone.utc)
                completed_at = task.completed_at
                if completed_at:
                    if completed_at.tzinfo is None:
                        completed_at = completed_at.replace(tzinfo=timezone.utc)
                    duration = (completed_at - started_at).total_seconds()

            print(f"  Task: {task.task_id}")
            print(f"    Model: {task.target_model}, App: {task.target_app_number}")
            print(f"    Subtasks: {total} total, {completed_count} completed, {failed_count} failed")
            print(f"    Current status: {task.status.value} → New status: {new_status.value}")
            print(f"    Duration: {duration:.1f}s" if duration else "    Duration: N/A")
            print(f"    Error: {task.error_message[:80]}...")
            print()

            if apply:
                task.status = new_status
                task.error_message = None
                if duration is not None:
                    task.actual_duration = duration

        if apply:
            db.session.commit()
            print(f"Applied fixes to {len(affected)} task(s).")
        else:
            print("DRY RUN — no changes made. Pass --apply to commit changes.")


if __name__ == '__main__':
    main()
