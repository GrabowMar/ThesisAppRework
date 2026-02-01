#!/usr/bin/env python3
"""Quick diagnostic for failures"""
import sys
sys.path.insert(0, '/app/src')
from app.factory import create_app
from app.models import PipelineExecution, AnalysisTask
from datetime import datetime, timedelta
from sqlalchemy import func

app = create_app()
with app.app_context():
    print("=" * 80)
    print("QUICK DIAGNOSTIC")
    print("=" * 80)

    # Recent pipelines
    print("\nRECENT PIPELINES:")
    pipelines = PipelineExecution.query.order_by(
        PipelineExecution.created_at.desc()
    ).limit(5).all()

    for p in pipelines:
        age = (datetime.utcnow() - p.created_at).total_seconds() / 60
        print(f"\n{p.pipeline_id}")
        print(f"  Status: {p.status} | Age: {age:.0f}m | Progress: {p.get_overall_progress():.1f}%")
        prog = p.progress
        gen = prog.get('generation', {})
        ana = prog.get('analysis', {})
        print(f"  Gen: {gen.get('completed', 0)}/{gen.get('total', 0)} (Fail: {gen.get('failed', 0)})")
        print(f"  Ana: {ana.get('completed', 0)}/{ana.get('total', 0)} (Fail: {ana.get('failed', 0)})")

    # Task status summary
    print("\n\nTASK STATUS SUMMARY:")
    task_stats = app.db.session.query(
        AnalysisTask.status,
        func.count(AnalysisTask.task_id)
    ).group_by(AnalysisTask.status).all()

    for status, count in task_stats:
        print(f"  {status:20} {count:5}")

    # Recent failed tasks
    print("\n\nRECENT FAILED TASKS (Last 30 min):")
    cutoff = datetime.utcnow() - timedelta(minutes=30)
    failed = AnalysisTask.query.filter(
        AnalysisTask.status == 'failed',
        AnalysisTask.updated_at >= cutoff
    ).order_by(AnalysisTask.updated_at.desc()).limit(5).all()

    print(f"Total: {len(failed)}")
    for task in failed:
        age = (datetime.utcnow() - task.updated_at).total_seconds() / 60
        print(f"  {task.task_id} - {age:.0f}m ago")

    print("\n" + "=" * 80)
