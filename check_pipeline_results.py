"""Check the pipeline test results."""
import sys
from pathlib import Path
import json

# Add src to path
src_dir = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_dir))

from app.factory import create_app
from app.models import PipelineExecution, AnalysisTask, GeneratedApplication

def main():
    """Check pipeline results."""
    app = create_app('development')

    with app.app_context():
        # Find the most recent pipeline
        pipeline = PipelineExecution.query.order_by(PipelineExecution.created_at.desc()).first()

        if not pipeline:
            print("[X] No pipelines found")
            return 1

        print("=" * 80)
        print(f"PIPELINE RESULTS: {pipeline.pipeline_id}")
        print("=" * 80)
        print(f"Name: {pipeline.name}")
        print(f"Status: {pipeline.status}")
        print(f"Stage: {pipeline.current_stage}")
        print(f"Job Index: {pipeline.current_job_index}")
        print(f"Created: {pipeline.created_at}")
        print(f"Updated: {pipeline.updated_at}")

        if pipeline.error_message:
            print(f"\n[X] Error: {pipeline.error_message}")

        # Print progress
        progress = pipeline.progress or {}
        print(f"\n{'-' * 80}")
        print("GENERATION PROGRESS:")
        print(f"{'-' * 80}")

        gen = progress.get('generation', {})
        print(f"Total: {gen.get('total', 0)}")
        print(f"Completed: {gen.get('completed', 0)}")
        print(f"Failed: {gen.get('failed', 0)}")
        print(f"Status: {gen.get('status', 'unknown')}")

        if 'results' in gen and gen['results']:
            print(f"\nGeneration Results:")
            for idx, result in enumerate(gen['results']):
                print(f"  [{idx}] Model: {result.get('model_slug', 'N/A')}")
                print(f"      Template: {result.get('template_slug', 'N/A')}")
                print(f"      App Number: {result.get('app_number', 'N/A')}")
                print(f"      Success: {result.get('success', False)}")
                if not result.get('success', False):
                    print(f"      Error: {result.get('error', 'N/A')}")

        print(f"\n{'-' * 80}")
        print("ANALYSIS PROGRESS:")
        print(f"{'-' * 80}")

        ana = progress.get('analysis', {})
        print(f"Total: {ana.get('total', 0)}")
        print(f"Completed: {ana.get('completed', 0)}")
        print(f"Failed: {ana.get('failed', 0)}")
        print(f"Status: {ana.get('status', 'unknown')}")

        if 'task_ids' in ana and ana['task_ids']:
            print(f"\nAnalysis Tasks: {len(ana['task_ids'])}")
            for task_id in ana['task_ids']:
                task = AnalysisTask.query.filter_by(task_id=task_id).first()
                if task:
                    print(f"  - {task_id}: Status={task.status}, Model={task.target_model}, App={task.target_app_number}")
                    if task.status in ['COMPLETED', 'PARTIAL_SUCCESS']:
                        if task.results:
                            print(f"    Results: {len(task.results.get('results', []))} tool results")
                    elif task.status == 'FAILED':
                        print(f"    Error: {task.error_message}")
                else:
                    print(f"  - {task_id}: NOT FOUND IN DATABASE")

        # Check generated applications
        print(f"\n{'-' * 80}")
        print("GENERATED APPLICATIONS:")
        print(f"{'-' * 80}")

        apps = GeneratedApplication.query.order_by(GeneratedApplication.created_at.desc()).limit(5).all()
        if apps:
            for app in apps:
                print(f"  - Model: {app.model_slug}, App: {app.app_number}")
                print(f"    Template: {app.template_slug}")
                print(f"    Status: {app.generation_status}")
                print(f"    Created: {app.created_at}")
        else:
            print("  No applications found")

        print(f"\n{'=' * 80}")

        return 0

if __name__ == '__main__':
    sys.exit(main())
