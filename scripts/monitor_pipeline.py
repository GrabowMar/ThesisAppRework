#!/usr/bin/env python3
"""Monitor a pipeline until completion and log progress."""
import sys
import time
from datetime import datetime

sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import PipelineExecution, AnalysisTask
from app.extensions import db
from app.constants import AnalysisStatus


def count_task_statuses(task_ids):
    if not task_ids:
        return {'pending': 0, 'running': 0, 'completed': 0, 'failed': 0, 'partial': 0}

    tasks = AnalysisTask.query.filter(AnalysisTask.task_id.in_(task_ids)).all()
    counts = {'pending': 0, 'running': 0, 'completed': 0, 'failed': 0, 'partial': 0}

    for t in tasks:
        if t.status == AnalysisStatus.PENDING:
            counts['pending'] += 1
        elif t.status == AnalysisStatus.RUNNING:
            counts['running'] += 1
        elif t.status == AnalysisStatus.COMPLETED:
            counts['completed'] += 1
        elif t.status == AnalysisStatus.PARTIAL_SUCCESS:
            counts['partial'] += 1
        else:
            counts['failed'] += 1

    return counts


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/monitor_pipeline.py <pipeline_id>")
        return 1

    pipeline_id = sys.argv[1]
    interval = 60

    app = create_app()
    with app.app_context():
        while True:
            pipeline = PipelineExecution.query.filter_by(pipeline_id=pipeline_id).first()
            if not pipeline:
                print(f"Pipeline not found: {pipeline_id}")
                return 1

            progress = pipeline.progress
            analysis_progress = progress.get('analysis', {}) if progress else {}
            main_task_ids = analysis_progress.get('main_task_ids', []) or analysis_progress.get('task_ids', [])

            counts = count_task_statuses(main_task_ids)
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            print(
                f"[{now}] status={pipeline.status} stage={pipeline.current_stage} "
                f"pending={counts['pending']} running={counts['running']} "
                f"completed={counts['completed']} partial={counts['partial']} failed={counts['failed']}"
            )

            if pipeline.status in ['completed', 'failed', 'partial_success', 'cancelled']:
                print(f"Pipeline finished with status: {pipeline.status}")
                return 0

            time.sleep(interval)


if __name__ == '__main__':
    sys.exit(main())
