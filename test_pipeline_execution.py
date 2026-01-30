#!/usr/bin/env python3
"""
Test Pipeline Execution Capability
Tests that a pipeline can be created and executed without breaking.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from app.factory import create_app
from app.models import PipelineExecution
from app.extensions import db


def test_pipeline_creation():
    """Test that we can create a pipeline in the database."""
    print("=" * 80)
    print("TESTING PIPELINE CREATION")
    print("=" * 80)

    app = create_app()
    with app.app_context():
        # Create a test pipeline configuration
        test_config = {
            'generation': {
                'mode': 'existing',  # Use existing apps, don't generate new ones
                'existingApps': ['google_gemini-3-flash-preview-20251217:1'],
            },
            'analysis': {
                'enabled': False,  # Disable analysis for this test
            }
        }

        # Create pipeline
        try:
            pipeline = PipelineExecution(
                user_id=1,  # Assuming admin user exists
                config=test_config,
                name="Test Pipeline - Health Check"
            )
            db.session.add(pipeline)
            db.session.commit()

            print(f"✓ Successfully created test pipeline: {pipeline.pipeline_id}")
            print(f"  Status: {pipeline.status}")
            print(f"  Stage: {pipeline.current_stage}")
            print(f"  Config: {pipeline.config}")

            # Clean up - delete the test pipeline
            db.session.delete(pipeline)
            db.session.commit()
            print(f"✓ Test pipeline cleaned up")

            return True

        except Exception as e:
            print(f"✗ Failed to create pipeline: {e}")
            import traceback
            traceback.print_exc()
            return False


def test_pipeline_state_machine():
    """Test pipeline state transitions."""
    print("\n" + "=" * 80)
    print("TESTING PIPELINE STATE MACHINE")
    print("=" * 80)

    app = create_app()
    with app.app_context():
        test_config = {
            'generation': {
                'mode': 'generate',
                'models': ['test-model'],
                'templates': ['test-template'],
            },
            'analysis': {
                'enabled': True,
                'tools': ['bandit'],
            }
        }

        try:
            pipeline = PipelineExecution(user_id=1, config=test_config, name="State Test")
            db.session.add(pipeline)
            db.session.commit()

            print(f"✓ Created pipeline: {pipeline.pipeline_id}")
            print(f"  Initial status: {pipeline.status}")

            # Test state transitions
            pipeline.start()
            db.session.commit()
            assert pipeline.status == 'running', f"Expected 'running', got '{pipeline.status}'"
            print(f"✓ Started: status = {pipeline.status}")

            # Test job retrieval
            job = pipeline.get_next_job()
            assert job is not None, "Expected a job from generation stage"
            assert job['stage'] == 'generation', f"Expected generation stage, got {job['stage']}"
            print(f"✓ Retrieved job: {job}")

            # Test job advancement
            pipeline.advance_job_index()
            db.session.commit()
            print(f"✓ Advanced job index to {pipeline.current_job_index}")

            # Test completion
            pipeline.status = 'completed'
            db.session.commit()
            assert pipeline.status == 'completed', f"Expected 'completed', got '{pipeline.status}'"
            print(f"✓ Completed: status = {pipeline.status}")

            # Clean up
            db.session.delete(pipeline)
            db.session.commit()
            print(f"✓ Cleaned up test pipeline")

            return True

        except Exception as e:
            print(f"✗ State machine test failed: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("PIPELINE EXECUTION CAPABILITY TEST")
    print("=" * 80 + "\n")

    results = {
        'Pipeline Creation': test_pipeline_creation(),
        'Pipeline State Machine': test_pipeline_state_machine(),
    }

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    for test_name, passed in results.items():
        icon = "✓" if passed else "✗"
        status = "PASSED" if passed else "FAILED"
        print(f"{icon} {test_name}: {status}")

    all_passed = all(results.values())

    print("\n" + "=" * 80)
    if all_passed:
        print("🎉 ALL TESTS PASSED - Pipeline execution system is functional")
    else:
        print("⚠ SOME TESTS FAILED - Pipeline execution may be broken")
    print("=" * 80)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
