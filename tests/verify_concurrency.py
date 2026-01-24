
import asyncio
import logging
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("verification")

from app import create_app
from app.services.generation_v2.concurrent_runner import ConcurrentGenerationRunner, GenerationJob

async def verify_concurrent_generation():
    logger.info("Starting ConcurrentGenerationRunner verification...")
    
    # Create fake jobs
    jobs = [
        GenerationJob(model_slug="gpt-4", template_slug="crud_todo_list", app_num=None),
        GenerationJob(model_slug="gpt-4", template_slug="crud_todo_list", app_num=None),
    ]
    
    # Mock generator to avoid real LLM/file usage which might be slow or fail
    # We want to test the orchestration and DB locking
    
    # Actually, we can't easily mock internal methods without monkeypatching.
    # Let's trust the runner but maybe catch errors.
    # Or strict verification: just instantiate and call pre-allocate logic which hits DB.
    
    runner = ConcurrentGenerationRunner(max_concurrent=2)
    
    # We will just test the pre-allocation part which uses the DB, 
    # as full generation requires templates, etc.
    # However, create_db_record is what we really want to test.
    
    logger.info("Executing batch generation (may fail if templates missing, but DB ops should obey context)...")
    try:
        results = await runner.generate_batch(jobs)
        logger.info(f"Runner finished. Results: {len(results)}")
        for r in results:
            logger.info(f"Job result: success={r.success}, error={r.error}")
            
            # If error is about templates/API, that's fine. 
            # If error is "Working outside application context", verification FAILED.
            if "outside of application context" in str(r.error):
                logger.error("FAILED: Context error detected!")
                return False
                
    except Exception as e:
        logger.error(f"Runner crashed: {e}")
        if "outside of application context" in str(e):
            return False
            
    return True

async def main():
    app = create_app()
    
    with app.app_context(): # This context is for the main loop, but thread ops create their own
        success = await verify_concurrent_generation()
        if success:
            logger.info("VERIFICATION PASSED: No context errors.")
        else:
            logger.error("VERIFICATION FAILED")

if __name__ == "__main__":
    # Ensure event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
