#!/usr/bin/env python3
"""Monitor a specific pipeline execution"""
import sys
import os
from datetime import datetime

sys.path.insert(0, '/app/src')
from app.factory import create_app
from app.models import PipelineExecution, AnalysisTask

def monitor_pipeline(pipeline_id):
    app = create_app()
    with app.app_context():
        pipeline = PipelineExecution.query.filter_by(pipeline_id=pipeline_id).first()

        if not pipeline:
            print(f"ERROR: Pipeline {pipeline_id} not found")
            return

        # Calculate runtime
        runtime = (datetime.utcnow() - pipeline.created_at).total_seconds()

        print("=" * 80)
        print(f"PIPELINE MONITORING - {datetime.now().strftime('%H:%M:%S')}")
        print("=" * 80)
        print(f"Pipeline ID: {pipeline.pipeline_id}")
        print(f"Name: {pipeline.name or 'N/A'}")
        print(f"Status: {pipeline.status}")
        print(f"Current Stage: {pipeline.current_stage}")
        print(f"Runtime: {runtime:.0f}s ({runtime/60:.1f}m)")
        print(f"Overall Progress: {pipeline.get_overall_progress():.1f}%")

        # Generation progress
        progress = pipeline.progress
        gen = progress.get('generation', {})
        print(f"\n📦 GENERATION STAGE:")
        print(f"   Total: {gen.get('total', 0)}")
        print(f"   Completed: {gen.get('completed', 0)}")
        print(f"   Failed: {gen.get('failed', 0)}")
        print(f"   Progress: {gen.get('completed', 0)}/{gen.get('total', 0)}")

        # Analysis progress
        analysis = progress.get('analysis', {})
        print(f"\n🔍 ANALYSIS STAGE:")
        print(f"   Total: {analysis.get('total', 0)}")
        print(f"   Completed: {analysis.get('completed', 0)}")
        print(f"   Failed: {analysis.get('failed', 0)}")
        print(f"   Progress: {analysis.get('completed', 0)}/{analysis.get('total', 0)}")

        # Recent task activity
        print(f"\n📋 RECENT TASK ACTIVITY:")
        recent_tasks = AnalysisTask.query.order_by(
            AnalysisTask.updated_at.desc()
        ).limit(5).all()

        for task in recent_tasks:
            age = (datetime.utcnow() - task.updated_at).total_seconds()
            print(f"   {task.task_id[:12]}... {task.status:15} {age:4.0f}s ago")

        print("=" * 80)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python monitor_pipeline.py <pipeline_id>")
        sys.exit(1)

    monitor_pipeline(sys.argv[1])
