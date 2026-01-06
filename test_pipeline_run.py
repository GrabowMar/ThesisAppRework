"""Test script to run a sample generation and analysis pipeline."""
import sys
from pathlib import Path

# Add src to path
src_dir = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_dir))

from app.factory import create_app
from app.extensions import db
from app.models import PipelineExecution, User
from app.models.pipeline import PipelineExecutionStatus
import json
import time

def create_test_user():
    """Create or get test user."""
    user = User.query.filter_by(username='test_user').first()
    if not user:
        user = User(
            username='test_user',
            email='test@example.com'
        )
        user.set_password('test_password')
        db.session.add(user)
        db.session.commit()
        print(f"[+] Created test user: {user.username} (ID: {user.id})")
    else:
        print(f"[+] Using existing test user: {user.username} (ID: {user.id})")
    return user

def start_test_pipeline(user_id):
    """Start a test pipeline with generation and analysis."""

    config = {
        'generation': {
            'mode': 'generate',
            'models': ['anthropic_claude-4.5-haiku-20251001'],
            'templates': ['simple_counter'],
            'options': {
                'use_auto_fix': False
            }
        },
        'analysis': {
            'enabled': True,
            'tools': ['semgrep', 'bandit', 'eslint'],
            'options': {
                'parallel': True,
                'maxConcurrentTasks': 2,
                'autoStartContainers': True,
                'stopAfterAnalysis': True
            }
        }
    }

    pipeline = PipelineExecution(
        user_id=user_id,
        name='Test Pipeline - Sample Generation & Analysis',
        config=config
    )

    db.session.add(pipeline)
    pipeline.start()  # This initializes the pipeline state
    db.session.commit()

    print(f"\n[+] Pipeline started successfully!")
    print(f"  Pipeline ID: {pipeline.pipeline_id}")
    print(f"  Status: {pipeline.status}")
    print(f"  Stage: {pipeline.current_stage}")
    print(f"  Config: {json.dumps(config, indent=2)}")

    return pipeline

def monitor_pipeline(pipeline_id, max_wait_seconds=300):
    """Monitor pipeline progress."""
    print(f"\n{'='*80}")
    print(f"MONITORING PIPELINE: {pipeline_id}")
    print(f"{'='*80}\n")

    start_time = time.time()
    last_status = None

    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait_seconds:
            print(f"\n[!] Timeout after {max_wait_seconds}s")
            break

        pipeline = PipelineExecution.query.filter_by(pipeline_id=pipeline_id).first()
        if not pipeline:
            print(f"[X] Pipeline {pipeline_id} not found!")
            break

        current_status = {
            'status': pipeline.status,
            'stage': pipeline.current_stage,
            'job_index': pipeline.current_job_index,
            'error': pipeline.error_message
        }

        # Only print if status changed
        if current_status != last_status:
            print(f"[{elapsed:.1f}s] Status: {pipeline.status} | Stage: {pipeline.current_stage} | Job: {pipeline.current_job_index}")

            # Print progress details
            progress = pipeline.progress or {}

            if 'generation' in progress:
                gen = progress['generation']
                print(f"  Generation: {gen.get('completed', 0)}/{gen.get('total', 0)} completed, {gen.get('failed', 0)} failed")

            if 'analysis' in progress:
                ana = progress['analysis']
                print(f"  Analysis: {ana.get('completed', 0)}/{ana.get('total', 0)} completed, {ana.get('failed', 0)} failed")
                if 'task_ids' in ana and ana['task_ids']:
                    print(f"    Task IDs: {', '.join(ana['task_ids'][:3])}{'...' if len(ana['task_ids']) > 3 else ''}")

            if pipeline.error_message:
                print(f"  [X] Error: {pipeline.error_message}")

            last_status = current_status

        # Check if pipeline is done
        if pipeline.status in [PipelineExecutionStatus.COMPLETED, PipelineExecutionStatus.FAILED, PipelineExecutionStatus.CANCELLED]:
            print(f"\n{'='*80}")
            print(f"PIPELINE FINISHED: {pipeline.status}")
            print(f"{'='*80}")
            print(f"Total time: {elapsed:.1f}s")

            # Print final summary
            progress = pipeline.progress or {}
            print(f"\nFinal Results:")
            print(f"  Generation: {progress.get('generation', {})}")
            print(f"  Analysis: {progress.get('analysis', {})}")

            return pipeline

        time.sleep(3)  # Poll every 3 seconds

    return None

def main():
    """Main test function."""
    print("=" * 80)
    print("PIPELINE TEST - Sample Generation & Analysis")
    print("=" * 80)

    # Create Flask app
    app = create_app('development')

    with app.app_context():
        # Create test user
        user = create_test_user()

        # Start pipeline
        pipeline = start_test_pipeline(user.id)

        # Monitor progress
        final_pipeline = monitor_pipeline(pipeline.pipeline_id, max_wait_seconds=600)

        if final_pipeline:
            print(f"\n[+] Pipeline test completed!")
            print(f"  Final Status: {final_pipeline.status}")

            # Analyze results
            if final_pipeline.status == PipelineExecutionStatus.COMPLETED:
                print(f"\n[++] SUCCESS - Pipeline completed successfully!")
                return 0
            else:
                print(f"\n[XX] FAILURE - Pipeline ended with status: {final_pipeline.status}")
                if final_pipeline.error_message:
                    print(f"   Error: {final_pipeline.error_message}")
                return 1
        else:
            print(f"\n[X] Pipeline monitoring ended without completion")
            return 1

if __name__ == '__main__':
    sys.exit(main())
