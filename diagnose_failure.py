#!/usr/bin/env python3
"""Comprehensive failure diagnostic"""
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, '/app/src')
from app.factory import create_app
from app.models import PipelineExecution, AnalysisTask, GeneratedApplication

def diagnose():
    app = create_app()
    with app.app_context():
        print("=" * 80)
        print("COMPREHENSIVE FAILURE DIAGNOSTIC")
        print("=" * 80)

        # 1. Check all recent pipelines
        print("\n1. ALL RECENT PIPELINES (Last 2 hours)")
        print("-" * 80)
        cutoff = datetime.utcnow() - timedelta(hours=2)
        pipelines = PipelineExecution.query.filter(
            PipelineExecution.created_at >= cutoff
        ).order_by(PipelineExecution.created_at.desc()).all()

        for p in pipelines:
            age = (datetime.utcnow() - p.created_at).total_seconds() / 60
            progress = p.progress
            gen = progress.get('generation', {})
            analysis = progress.get('analysis', {})

            status_icon = "❌" if p.status == 'failed' else "⏸️" if p.status == 'running' else "✅"

            print(f"\n{status_icon} {p.pipeline_id}")
            print(f"   Status: {p.status} | Age: {age:.0f}m | Progress: {p.get_overall_progress():.1f}%")
            print(f"   Gen: {gen.get('completed', 0)}/{gen.get('total', 0)} (Failed: {gen.get('failed', 0)})")
            print(f"   Analysis: {analysis.get('completed', 0)}/{analysis.get('total', 0)} (Failed: {analysis.get('failed', 0)})")

        # 2. Check failed tasks
        print("\n\n2. FAILED TASKS (Last 30 min)")
        print("-" * 80)
        cutoff = datetime.utcnow() - timedelta(minutes=30)
        failed = AnalysisTask.query.filter(
            AnalysisTask.status == 'failed',
            AnalysisTask.updated_at >= cutoff
        ).order_by(AnalysisTask.updated_at.desc()).all()

        print(f"Total failed tasks: {len(failed)}")
        for task in failed[:5]:
            age = (datetime.utcnow() - task.updated_at).total_seconds() / 60
            result = task.results or {}
            error = result.get('error', 'No error message')
            print(f"\n❌ {task.task_id}")
            print(f"   App: {task.app_slug}")
            print(f"   Age: {age:.1f}m ago")
            print(f"   Error: {error[:200]}")

        # 3. Check running tasks
        print("\n\n3. CURRENTLY RUNNING TASKS")
        print("-" * 80)
        running = AnalysisTask.query.filter_by(status='running').all()
        print(f"Total running: {len(running)}")
        for task in running[:10]:
            age = (datetime.utcnow() - task.updated_at).total_seconds() / 60
            print(f"   {task.task_id[:15]}... | {task.app_slug:30} | {age:.0f}m running")

        # 4. Check pending tasks
        print("\n\n4. PENDING TASKS (Waiting to run)")
        print("-" * 80)
        pending = AnalysisTask.query.filter_by(status='pending').all()
        print(f"Total pending: {len(pending)}")
        for task in pending[:10]:
            age = (datetime.utcnow() - task.created_at).total_seconds() / 60
            print(f"   {task.task_id[:15]}... | {task.app_slug:30} | {age:.0f}m waiting")

        # 5. Check failed apps
        print("\n\n5. FAILED APP GENERATIONS (Last 30 min)")
        print("-" * 80)
        cutoff = datetime.utcnow() - timedelta(minutes=30)
        failed_apps = GeneratedApplication.query.filter(
            GeneratedApplication.status == 'failed',
            GeneratedApplication.created_at >= cutoff
        ).all()

        print(f"Total failed apps: {len(failed_apps)}")
        for app in failed_apps[:5]:
            print(f"\n❌ {app.app_slug}")
            print(f"   Model: {app.model_slug}")
            if app.error_message:
                print(f"   Error: {app.error_message[:200]}")

        # 6. System capacity
        print("\n\n6. SYSTEM CAPACITY")
        print("-" * 80)
        total_running = AnalysisTask.query.filter_by(status='running').count()
        total_pending = AnalysisTask.query.filter_by(status='pending').count()
        print(f"Running tasks: {total_running} (Max: 10)")
        print(f"Pending tasks: {total_pending}")
        print(f"Queue status: {'CONGESTED' if total_running >= 10 else 'Available slots'}")

        print("\n" + "=" * 80)

if __name__ == "__main__":
    diagnose()
