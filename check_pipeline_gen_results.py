"""Check pipeline generation results."""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import PipelineExecution
import json

app = create_app()

with app.app_context():
    # Get latest pipeline
    pipeline = PipelineExecution.query.order_by(PipelineExecution.created_at.desc()).first()
    
    if not pipeline:
        print("No pipeline found!")
        sys.exit(1)
    
    print(f"Pipeline: {pipeline.pipeline_id}")
    print(f"Status: {pipeline.status}")
    print()
    
    # Check generation results
    gen_progress = pipeline.progress.get('generation', {})
    gen_results = gen_progress.get('results', [])
    
    print(f"Generation Results: {len(gen_results)} total")
    print()
    
    for i, result in enumerate(gen_results):
        model = result.get('model_slug', 'unknown')
        app_num = result.get('app_number') or result.get('app_num', '?')
        success = result.get('success', False)
        template = result.get('template_slug', 'unknown')
        error = result.get('error', '')
        
        print(f"{i}: {model}/app{app_num} - {'SUCCESS' if success else 'FAILED'} - {template}")
        if error:
            print(f"   Error: {error[:100]}")
    
    print()
    print(f"Analysis would stop at job_index {len(gen_results)}")
    print()
    
    # Check selected apps
    selected_apps = pipeline.config.get('generation', {}).get('selected_apps', [])
    print(f"Selected Apps: {selected_apps}")
