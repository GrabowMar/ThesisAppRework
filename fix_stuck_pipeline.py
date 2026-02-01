#!/usr/bin/env python3
"""Fix stuck pipelines by completing generation stage"""
import sys
sys.path.insert(0, '/app/src')
from app.factory import create_app
from app.models import PipelineExecution
from app.extensions import db

app = create_app()
with app.app_context():
    # Get stuck pipelines
    stuck = PipelineExecution.query.filter_by(
        status='running',
        current_stage='generation'
    ).all()

    print(f"Found {len(stuck)} potentially stuck pipelines")

    for p in stuck:
        progress = p.progress
        gen = progress.get('generation', {})

        total = gen.get('total', 0)
        completed = gen.get('completed', 0)
        failed = gen.get('failed', 0)
        processed = completed + failed

        print(f"\nPipeline: {p.pipeline_id}")
        print(f"  Gen: {completed}/{total} completed, {failed} failed")
        print(f"  Processed: {processed}/{total}")
        print(f"  Gen status: {gen.get('status')}")

        # If all jobs are processed (completed + failed == total)
        if processed >= total and gen.get('status') != 'completed':
            print(f"  ✅ Marking generation as completed (all jobs processed)")

            # Update generation status
            progress['generation']['status'] = 'completed'
            p.progress = progress

            # Check if analysis should run
            analysis_enabled = progress.get('analysis', {}).get('status') != 'skipped'

            if analysis_enabled:
                print(f"  ✅ Transitioning to analysis stage")
                p.current_stage = 'analysis'
                p.current_job_index = 0
                progress['analysis']['status'] = 'running'
                p.progress = progress
            else:
                print(f"  ✅ Completing pipeline (analysis skipped)")
                p.status = 'completed'
                p.current_stage = 'done'

            db.session.commit()
            print(f"  ✅ Fixed!")
        elif processed < total:
            print(f"  ⚠️  Still waiting for {total - processed} jobs to complete")
        else:
            print(f"  ℹ️  Already in correct state")

    print("\n" + "=" * 80)
    print("DONE")
