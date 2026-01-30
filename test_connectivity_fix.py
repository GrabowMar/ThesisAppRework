#!/usr/bin/env python3
"""
Test script to verify analyzer connectivity fix by running a real pipeline.
This will generate 2 apps and analyze them with all 4 analyzer services.
"""

import sys
import os
import time
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from app.factory import create_app
from app.models import PipelineExecution, AnalysisTask
from app.extensions import db


def run_test_pipeline():
    """Run a small test pipeline to verify analyzer connectivity."""
    print("=" * 80)
    print("REAL PIPELINE CONNECTIVITY TEST")
    print("=" * 80)
    print()

    app = create_app()
    with app.app_context():
        # Create test pipeline configuration
        test_config = {
            'generation': {
                'mode': 'generate',
                'models': ['google/gemini-flash-1.5-8b'],  # Use fast model
                'templates': ['todo_app', 'note_taking_app'],  # Just 2 apps
            },
            'analysis': {
                'enabled': True,
                'tools': [
                    'bandit', 'pylint', 'eslint',  # Static tools
                    'zap', 'curl',  # Dynamic tools
                    'locust',  # Performance tool
                    'requirements-scanner'  # AI tool
                ],
            }
        }

        # Create pipeline
        print("Creating test pipeline...")
        pipeline = PipelineExecution(
            user_id=1,
            config=test_config,
            name="Connectivity Fix Test Pipeline"
        )
        db.session.add(pipeline)
        db.session.commit()

        print(f"✓ Pipeline created: {pipeline.pipeline_id}")
        print(f"  Status: {pipeline.status}")
        print()

        # Start pipeline
        print("Starting pipeline...")
        pipeline.start()
        db.session.commit()
        print(f"✓ Pipeline started: {pipeline.status}")
        print()

        print("Pipeline Details:")
        print(f"  ID: {pipeline.pipeline_id}")
        print(f"  Models: {test_config['generation']['models']}")
        print(f"  Templates: {test_config['generation']['templates']}")
        print(f"  Expected apps: {len(test_config['generation']['models']) * len(test_config['generation']['templates'])}")
        print()

        print("=" * 80)
        print("MONITORING PIPELINE EXECUTION")
        print("=" * 80)
        print()
        print("The pipeline is now running. Monitor progress with:")
        print(f"  docker compose exec web python3 check_pipeline.py")
        print()
        print("Check analysis task status:")
        print(f"  docker compose exec web python3 -c \"")
        print(f"import sys")
        print(f"sys.path.insert(0, '/app/src')")
        print(f"from app.factory import create_app")
        print(f"from app.models import AnalysisTask")
        print(f"app = create_app()")
        print(f"with app.app_context():")
        print(f"    tasks = AnalysisTask.query.all()")
        print(f"    service_counts = {{}}")
        print(f"    for task in tasks:")
        print(f"        if not task.is_main_task and task.service_name:")
        print(f"            service_counts[task.service_name] = service_counts.get(task.service_name, 0) + 1")
        print(f"    for service, count in sorted(service_counts.items()):")
        print(f"        print(f'{{service}}: {{count}} tasks')")
        print(f"\"")
        print()
        print("=" * 80)
        print()

        # Wait a moment for the pipeline to start processing
        print("Waiting 30 seconds for pipeline to begin processing...")
        time.sleep(30)

        # Check initial progress
        db.session.refresh(pipeline)
        progress = pipeline.progress

        print()
        print("=" * 80)
        print("INITIAL PROGRESS CHECK")
        print("=" * 80)
        print(f"Pipeline status: {pipeline.status}")
        print(f"Current stage: {pipeline.current_stage}")
        print(f"Overall progress: {pipeline.get_overall_progress()}%")
        print()

        gen_progress = progress.get('generation', {})
        print("Generation:")
        print(f"  Total: {gen_progress.get('total', 0)}")
        print(f"  Completed: {gen_progress.get('completed', 0)}")
        print(f"  Failed: {gen_progress.get('failed', 0)}")
        print()

        analysis_progress = progress.get('analysis', {})
        print("Analysis:")
        print(f"  Total: {analysis_progress.get('total', 0)}")
        print(f"  Completed: {analysis_progress.get('completed', 0)}")
        print(f"  Failed: {analysis_progress.get('failed', 0)}")
        print()

        # Check analysis tasks by service
        tasks = AnalysisTask.query.all()
        if tasks:
            print("Analysis Tasks by Service:")
            service_counts = {}
            service_status = {}

            for task in tasks:
                if not task.is_main_task and task.service_name:
                    service = task.service_name
                    service_counts[service] = service_counts.get(service, 0) + 1

                    if service not in service_status:
                        service_status[service] = {'completed': 0, 'failed': 0, 'running': 0, 'pending': 0}

                    status = task.status.value
                    if status in ['completed', 'partial_success']:
                        service_status[service]['completed'] += 1
                    elif status == 'failed':
                        service_status[service]['failed'] += 1
                    elif status in ['running', 'queued']:
                        service_status[service]['running'] += 1
                    else:
                        service_status[service]['pending'] += 1

            for service in sorted(service_counts.keys()):
                total = service_counts[service]
                status = service_status[service]
                print(f"  {service}: {total} tasks")
                print(f"    Completed: {status['completed']}, Failed: {status['failed']}, Running: {status['running']}, Pending: {status['pending']}")

            # Check for connectivity errors
            print()
            print("Checking for connectivity errors...")
            connectivity_errors = 0
            for task in tasks:
                if task.error_message and 'No reachable endpoints' in task.error_message:
                    connectivity_errors += 1
                    print(f"  ✗ {task.task_id}: {task.service_name} - {task.error_message}")

            if connectivity_errors == 0:
                print("  ✓ No connectivity errors found!")
            else:
                print(f"  ✗ Found {connectivity_errors} connectivity errors")
        else:
            print("No analysis tasks created yet (pipeline may still be in generation stage)")

        print()
        print("=" * 80)
        print("TEST PIPELINE SUMMARY")
        print("=" * 80)
        print(f"Pipeline ID: {pipeline.pipeline_id}")
        print(f"Status: {pipeline.status}")
        print()
        print("The pipeline will continue running in the background.")
        print("Check back in a few minutes to see final results.")
        print()
        print("To monitor progress:")
        print("  docker compose logs -f celery-worker")
        print()
        print("To check final results when complete:")
        print(f"  docker compose exec web python3 -c \\")
        print(f"    \"import sys; sys.path.insert(0, '/app/src'); \\")
        print(f"     from app.factory import create_app; \\")
        print(f"     from app.models import PipelineExecution; \\")
        print(f"     app = create_app(); \\")
        print(f"     with app.app_context(): \\")
        print(f"       p = PipelineExecution.query.filter_by(pipeline_id='{pipeline.pipeline_id}').first(); \\")
        print(f"       print(f'Status: {{p.status}}'); \\")
        print(f"       print(f'Progress: {{p.get_overall_progress()}}%'); \\")
        print(f"       print(f'Generation: {{p.progress.get(\\'generation\\', {{}})}}'); \\")
        print(f"       print(f'Analysis: {{p.progress.get(\\'analysis\\', {{}})}}')\"")
        print()
        print("=" * 80)

        return pipeline.pipeline_id


if __name__ == "__main__":
    try:
        pipeline_id = run_test_pipeline()
        print(f"\n✓ Test pipeline initiated: {pipeline_id}")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
