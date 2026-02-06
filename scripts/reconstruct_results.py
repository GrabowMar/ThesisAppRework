#!/usr/bin/env python3
"""
Reconstruct missing result files from database.
Finds tasks marked 'completed' with result_summary in DB but no files on disk.
"""
import json
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.factory import create_app
from app.models import AnalysisTask


def reconstruct_results(dry_run: bool = False):
    """Reconstruct missing result files from database."""
    app = create_app()
    
    with app.app_context():
        results_base = Path('/app/results')
        
        # Find all completed main tasks
        main_tasks = AnalysisTask.query.filter(
            AnalysisTask.is_main_task == True,
            AnalysisTask.status == 'completed'
        ).all()
        
        reconstructed = 0
        skipped = 0
        failed = 0
        
        for main_task in main_tasks:
            model = main_task.target_model
            app_num = main_task.target_app_number
            task_id = main_task.task_id
            
            # Check if results exist on disk
            app_dir = results_base / model / f'app{app_num}'
            task_dir = app_dir / task_id
            services_dir = task_dir / 'services'
            
            # Skip if already has results
            if services_dir.exists() and any(services_dir.glob('*.json')):
                skipped += 1
                continue
            
            # Get subtasks with results
            subtasks = AnalysisTask.query.filter_by(
                parent_task_id=task_id
            ).all()
            
            if not subtasks:
                print(f"[SKIP] {model}/app{app_num}/{task_id}: No subtasks found")
                continue
            
            # Check if all subtasks have results
            all_have_results = all(
                t.result_summary for t in subtasks if t.service_name
            )
            
            if not all_have_results:
                print(f"[SKIP] {model}/app{app_num}/{task_id}: Missing subtask results")
                continue
            
            if dry_run:
                print(f"[DRY-RUN] Would reconstruct: {model}/app{app_num}/{task_id}")
                reconstructed += 1
                continue
            
            try:
                # Create directories
                services_dir.mkdir(parents=True, exist_ok=True)
                
                consolidated = {
                    'task_id': task_id,
                    'model_slug': model,
                    'app_number': app_num,
                    'status': 'success',
                    'reconstructed_at': datetime.utcnow().isoformat(),
                    'services': {}
                }
                
                for subtask in subtasks:
                    if not subtask.service_name or not subtask.result_summary:
                        continue
                    
                    # Parse result_summary
                    result = subtask.result_summary
                    if isinstance(result, str):
                        result = json.loads(result)
                    
                    service_name = subtask.service_name
                    
                    # Write individual service file
                    service_file = services_dir / f'{service_name}.json'
                    with open(service_file, 'w') as f:
                        json.dump(result, f, indent=2, default=str)
                    
                    # Add to consolidated
                    consolidated['services'][service_name] = {
                        'status': result.get('status', 'success'),
                        'file': f'services/{service_name}.json'
                    }
                
                # Write consolidated.json
                consolidated_file = task_dir / 'consolidated.json'
                with open(consolidated_file, 'w') as f:
                    json.dump(consolidated, f, indent=2, default=str)
                
                print(f"[OK] Reconstructed: {model}/app{app_num}/{task_id}")
                reconstructed += 1
                
            except Exception as e:
                print(f"[ERROR] {model}/app{app_num}/{task_id}: {e}")
                failed += 1
        
        print(f"\n=== Summary ===")
        print(f"Reconstructed: {reconstructed}")
        print(f"Already existed: {skipped}")
        print(f"Failed: {failed}")
        
        return reconstructed, skipped, failed


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    args = parser.parse_args()
    
    reconstruct_results(dry_run=args.dry_run)
