#!/usr/bin/env python3
"""
Comprehensive Pipeline and Task Orchestration Test
Tests the automation pipeline and task execution to ensure no breakage.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from app.factory import create_app
from app.models import PipelineExecution, AnalysisTask
from app.extensions import db
import json


def test_pipeline_integrity():
    """Test pipeline database integrity and recent executions."""
    print("=" * 80)
    print("PIPELINE INTEGRITY TEST")
    print("=" * 80)

    app = create_app()
    with app.app_context():
        # Check total pipelines
        total_pipelines = PipelineExecution.query.count()
        print(f"\n✓ Total pipelines in database: {total_pipelines}")

        if total_pipelines == 0:
            print("⚠ WARNING: No pipelines found in database")
            return False

        # Check recent pipelines
        recent_pipelines = PipelineExecution.query.order_by(
            PipelineExecution.created_at.desc()
        ).limit(5).all()

        print(f"\n📊 Recent Pipeline Executions (last {len(recent_pipelines)}):")
        print("-" * 80)

        all_successful = True
        for p in recent_pipelines:
            progress = p.get_overall_progress()
            status_icon = "✓" if p.status == "completed" else "✗"
            print(f"{status_icon} Pipeline: {p.pipeline_id}")
            print(f"  Name: {p.name or 'Unnamed'}")
            print(f"  Status: {p.status}")
            print(f"  Stage: {p.current_stage}")
            print(f"  Progress: {progress}%")
            print(f"  Created: {p.created_at}")

            # Check progress details
            prog_data = p.progress
            gen = prog_data.get('generation', {})
            analysis = prog_data.get('analysis', {})

            print(f"  Generation: {gen.get('completed', 0)}/{gen.get('total', 0)} "
                  f"(failed: {gen.get('failed', 0)})")
            print(f"  Analysis: {analysis.get('completed', 0)}/{analysis.get('total', 0)} "
                  f"(failed: {analysis.get('failed', 0)})")

            if p.error_message:
                print(f"  ⚠ Error: {p.error_message}")
                all_successful = False

            print()

        # Check for stuck pipelines
        running_pipelines = PipelineExecution.query.filter_by(
            status='running'
        ).all()

        if running_pipelines:
            print(f"⚠ WARNING: {len(running_pipelines)} pipeline(s) in 'running' state")
            for p in running_pipelines:
                print(f"  - {p.pipeline_id} (created: {p.created_at})")
            all_successful = False
        else:
            print("✓ No stuck pipelines found")

        return all_successful


def test_task_orchestration():
    """Test analysis task execution and status."""
    print("\n" + "=" * 80)
    print("TASK ORCHESTRATION TEST")
    print("=" * 80)

    app = create_app()
    with app.app_context():
        # Check total tasks
        total_tasks = AnalysisTask.query.count()
        print(f"\n✓ Total analysis tasks in database: {total_tasks}")

        if total_tasks == 0:
            print("⚠ WARNING: No analysis tasks found")
            return False

        # Check task status distribution
        statuses = db.session.query(
            AnalysisTask.status,
            db.func.count(AnalysisTask.id)
        ).group_by(AnalysisTask.status).all()

        print(f"\n📊 Task Status Distribution:")
        print("-" * 80)
        for status, count in statuses:
            print(f"  {status}: {count}")

        # Check recent tasks
        recent_tasks = AnalysisTask.query.order_by(
            AnalysisTask.created_at.desc()
        ).limit(10).all()

        print(f"\n📋 Recent Tasks (last {len(recent_tasks)}):")
        print("-" * 80)

        all_successful = True
        for t in recent_tasks:
            status_icon = "✓" if t.status == "COMPLETED" else "⚠" if t.status == "RUNNING" else "✗"
            print(f"{status_icon} Task: {t.task_id}")
            print(f"  Status: {t.status}")
            print(f"  Model: {t.target_model}")
            print(f"  App: {t.target_app_number}")
            print(f"  Created: {t.created_at}")
            print(f"  Service: {t.service_name or 'Main Task' if t.is_main_task else 'N/A'}")

            if t.status == "FAILED":
                all_successful = False
                if t.error_message:
                    print(f"  ⚠ Error: {t.error_message[:100]}")

            print()

        # Check for stuck tasks
        stuck_tasks = AnalysisTask.query.filter(
            AnalysisTask.status.in_(['QUEUED', 'RUNNING'])
        ).all()

        if stuck_tasks:
            print(f"⚠ WARNING: {len(stuck_tasks)} task(s) potentially stuck in QUEUED/RUNNING")
            all_successful = False
        else:
            print("✓ No stuck tasks found")

        return all_successful


def test_celery_connectivity():
    """Test Celery/Redis connectivity."""
    print("\n" + "=" * 80)
    print("CELERY CONNECTIVITY TEST")
    print("=" * 80)

    try:
        from celery import Celery
        import redis

        # Test Redis connection
        print("\n🔍 Testing Redis connection...")
        r = redis.Redis(host='redis', port=6379, db=0, socket_connect_timeout=2)
        r.ping()
        print("✓ Redis connection successful")

        # Test Celery broker
        print("\n🔍 Testing Celery broker...")
        celery_app = Celery('app', broker='redis://redis:6379/0')
        inspect = celery_app.control.inspect(timeout=2)

        stats = inspect.stats()
        if stats:
            print(f"✓ Celery worker(s) found: {list(stats.keys())}")
            for worker_name, worker_stats in stats.items():
                print(f"  Worker: {worker_name}")
                print(f"    Pool: {worker_stats.get('pool', {})}")
            return True
        else:
            print("✗ No Celery workers responding")
            return False

    except redis.ConnectionError as e:
        print(f"✗ Redis connection failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Celery connectivity test failed: {e}")
        return False


def test_analyzer_services():
    """Test analyzer service health."""
    print("\n" + "=" * 80)
    print("ANALYZER SERVICES TEST")
    print("=" * 80)

    import socket

    services = [
        ('static-analyzer', 2001),
        ('dynamic-analyzer', 2002),
        ('performance-tester', 2003),
        ('ai-analyzer', 2004),
    ]

    all_healthy = True
    for service_name, port in services:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((service_name, port))
            sock.close()

            if result == 0:
                print(f"✓ {service_name}:{port} - Accessible")
            else:
                print(f"✗ {service_name}:{port} - Not accessible")
                all_healthy = False
        except Exception as e:
            print(f"✗ {service_name}:{port} - Error: {e}")
            all_healthy = False

    return all_healthy


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("PIPELINE AND TASK ORCHESTRATION COMPREHENSIVE TEST")
    print("=" * 80)

    results = {}

    # Run tests
    results['Pipeline Integrity'] = test_pipeline_integrity()
    results['Task Orchestration'] = test_task_orchestration()
    results['Celery Connectivity'] = test_celery_connectivity()
    results['Analyzer Services'] = test_analyzer_services()

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    for test_name, passed in results.items():
        icon = "✓" if passed else "✗"
        print(f"{icon} {test_name}: {'PASSED' if passed else 'FAILED'}")

    all_passed = all(results.values())

    print("\n" + "=" * 80)
    if all_passed:
        print("🎉 ALL TESTS PASSED - System is healthy")
    else:
        print("⚠ SOME TESTS FAILED - Review issues above")
    print("=" * 80)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
