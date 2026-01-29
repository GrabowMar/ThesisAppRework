import sys
import os
import json
import uuid
from datetime import datetime, timezone

# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from app.factory import create_app
from app.extensions import db
from app.models import ModelCapability, PipelineExecution, PipelineExecutionStatus, User
from app.services.generation_v2.service import GenerationService

def start_pipeline():
    app = create_app()
    with app.app_context():
        # 1. Get all available model slugs
        available_models = {m.canonical_slug: m for m in ModelCapability.query.all()}
        print(f"Found {len(available_models)} available models in system.")

        # 2. Target models from docs/models_to_test.md (mapped to slugs)
        # Note: In a real scenario, we'd parse the markdown. For now, I'll use a mapping.
        target_model_names = [
            "Qwen3-Coder-30B-A3B",
            "DeepSeek-R1-0528",
            "Gemini-2.5-Flash",
            "Claude-Sonnet-4.5",
            "GPT-5-Mini",
            "Llama-3.3-70B",
            "Qwen3-32B",
            "GLM-4.6",
            "Mistral-Small-24B-2501",
            "GPT-4o-Mini"
        ]
        
        # Fuzzy mapping logic (simplified for this automation script)
        slugs_to_run = []
        for name in target_model_names:
            found = False
            # Check for direct match or partial match
            for slug in available_models:
                if name.lower().replace("-", "") in slug.lower().replace("-", "").replace("_", ""):
                    slugs_to_run.append(slug)
                    found = True
                    break
            if not found:
                print(f"Warning: Could not find slug for {name}")

        if not slugs_to_run:
            print("No models found to run. Exiting.")
            return

        print(f"Selected {len(slugs_to_run)} models for analysis: {slugs_to_run}")

        # 3. Get all templates
        gen_svc = GenerationService()
        templates = gen_svc.get_template_catalog()
        template_slugs = [t['slug'] for t in templates]
        print(f"Found {len(template_slugs)} templates.")

        # 4. Create Pipeline Configuration
        # We want END-TO-END: Generation AND Analysis
        config = {
            'generation': {
                'mode': 'generate',
                'models': slugs_to_run,
                'templates': template_slugs,
                'options': {
                    'parallel': True,
                    'maxConcurrentTasks': 4, # Increased for speed
                }
            },
            'analysis': {
                'enabled': True,
                'tools': [], # Empty list = use all available tools
                'options': {
                    'parallel': True,
                    'maxConcurrentTasks': 6, # High parallelism for analysis
                    'autoStartContainers': True,
                    'stopAfterAnalysis': True,
                }
            }
        }

        # 5. Create and start PipelineExecution
        # Get admin user (id=1 usually)
        admin = User.query.get(1)
        if not admin:
            print("Error: Could not find admin user (id=1)")
            return

        pipeline = PipelineExecution(
            user_id=admin.id,
            config=config,
            name=f"Empirical Evaluation: Top 10 Models ({datetime.now().strftime('%Y-%m-%d')})"
        )
        
        db.session.add(pipeline)
        pipeline.start()
        db.session.commit()

        print(f"Successfully started pipeline: {pipeline.pipeline_id}")
        print(f"Total jobs: {pipeline.progress['generation']['total']} generations + analysis")

if __name__ == "__main__":
    start_pipeline()
