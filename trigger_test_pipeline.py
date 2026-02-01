#!/usr/bin/env python3
"""Trigger a small test pipeline for monitoring"""
import sys
import os
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from app.factory import create_app
from app.extensions import db
from app.models import ModelCapability, PipelineExecution, User
from app.services.generation_v2.service import GenerationService
from datetime import datetime

def start_test_pipeline():
    app = create_app()
    with app.app_context():
        # Get a few models for quick testing
        all_models = ModelCapability.query.limit(2).all()
        model_slugs = [m.canonical_slug for m in all_models]

        if not model_slugs:
            print("ERROR: No models found in database")
            return

        # Get a couple of templates
        gen_svc = GenerationService()
        templates = gen_svc.get_template_catalog()[:2]  # Just first 2 templates
        template_slugs = [t['slug'] for t in templates]

        print(f"Creating test pipeline:")
        print(f"  Models: {model_slugs}")
        print(f"  Templates: {template_slugs}")
        print(f"  Total apps to generate: {len(model_slugs) * len(template_slugs)}")

        # Create pipeline configuration
        config = {
            'generation': {
                'mode': 'generate',
                'models': model_slugs,
                'templates': template_slugs,
                'options': {
                    'parallel': True,
                    'maxConcurrentTasks': 2,
                }
            },
            'analysis': {
                'enabled': True,
                'tools': [],  # All available tools
                'options': {
                    'parallel': True,
                    'maxConcurrentTasks': 4,
                    'autoStartContainers': True,
                    'stopAfterAnalysis': True,
                }
            }
        }

        # Get admin user
        admin = User.query.first()
        if not admin:
            print("ERROR: No users found")
            return

        # Create and start pipeline
        pipeline = PipelineExecution(
            user_id=admin.id,
            config=config,
            name=f"Test Pipeline - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )

        db.session.add(pipeline)
        pipeline.start()
        db.session.commit()

        print(f"\n✅ Pipeline started successfully!")
        print(f"Pipeline ID: {pipeline.pipeline_id}")
        print(f"Status: {pipeline.status}")
        print(f"Stage: {pipeline.current_stage}")

        return pipeline.pipeline_id

if __name__ == "__main__":
    pipeline_id = start_test_pipeline()
    if pipeline_id:
        print(f"\nMonitor with: docker exec thesisapprework-web-1 python check_pipeline.py")
