import asyncio
import os
import sys
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to python path
project_root = Path(os.getcwd())
sys.path.append(str(project_root / 'src'))

# Attempt to load .env if not loaded
env_path = project_root / '.env'
if env_path.exists():
    print(f"Loading .env from {env_path}")
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                if key not in os.environ:
                    os.environ[key] = val.strip('"\'')

from app.services.generation_v2.concurrent_runner import ConcurrentGenerationRunner, GenerationJob
from app.factory import create_cli_app

# Mock DB dependencies
# We need to patch ModelCapability used in _get_openrouter_model and _get_model_context_window
from unittest.mock import MagicMock, patch
from app.services.generation_v2.code_generator import CodeGenerator

async def main():
    if 'OPENROUTER_API_KEY' not in os.environ:
        print("ERROR: OPENROUTER_API_KEY not found in environment or .env file.")
        print("Skipping generation to avoid crash.")
        return

    # Use CLI app context to ensure DB and config is ready
    app = create_cli_app()
    with app.app_context():
        # Patch CodeGenerator internal methods to bypass DB lookups for CLI test
        with patch.object(CodeGenerator, '_get_openrouter_model', return_value="qwen/qwen3-coder-30b-a3b-instruct"), \
             patch.object(CodeGenerator, '_get_model_context_window', return_value=32000):
            
            # Use the same runner as the pipeline!
            # This ensures individual generation follows the exact same logic/steps.
            runner = ConcurrentGenerationRunner(
                max_concurrent=1,  # CLI usually sequential, but uses the same async machinery
                inter_job_delay=0.5
            )
            print("ConcurrentGenerationRunner ready.")
            
            apps_to_gen = [
                {'template': 'crud_todo_list', 'app_num': 1},
                # {'template': 'productivity_notes', 'app_num': 2} 
            ]
            
            # Prepare jobs
            jobs = []
            for app_def in apps_to_gen:
                slug = app_def['template']
                num = app_def['app_num']
                print(f"Queueing job: {slug} (App {num})")
                
                # Note: We use the runner's job structure
                jobs.append(GenerationJob(
                    model_slug='qwen_qwen3-coder-30b-a3b-instruct',
                    template_slug=slug,
                    app_num=num,
                    batch_id='cli-manual-run'
                ))
            
            print(f"\n--- Starting Batch Generation ({len(jobs)} jobs) ---")
            import time
            start_time = time.time()
            
            # execute via runner
            results = await runner.generate_batch(jobs, batch_id='cli-manual-run')
            
            display_success = 0
            for res in results:
                status = "SUCCESS" if res.success else "FAILED"
                print(f"Job {res.job_index} ({res.template_slug}): {status}")
                if res.error:
                    print(f"  Error: {res.error}")
                if res.success:
                    display_success += 1
                    
                    # In CLI mode, we might want to verify files exist or move them?
                    # The runner saves them to generated/apps/{model}/{app_name}
                    # The original script moved them to specific paths.
                    # ConcurrentGenerationRunner handles standard saving.
                    # We can print path:
                    print(f"  Artifacts saved to standard output directory.")
            
            print(f"\nTotal time: {time.time() - start_time:.1f}s")
            print(f"Completed: {display_success}/{len(jobs)}")

if __name__ == "__main__":
    asyncio.run(main())
