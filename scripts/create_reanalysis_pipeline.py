"""
Create Re-Analysis Pipeline
===========================

This script creates a new pipeline to re-analyze existing applications.

The script creates a pipeline configuration for re-running analysis on previously
generated applications without regenerating the code. This is useful for:

- Testing new analysis tools on existing apps
- Re-running failed analyses
- Comparing analysis results over time
- Validating fixes to analysis tools

Configuration:
- Uses existing applications (no regeneration)
- Runs full analysis suite (static, dynamic, performance, AI)
- Parallel execution with configurable concurrency
- Auto-starts analysis containers

Usage:
    python scripts/create_reanalysis_pipeline.py

The pipeline will be created with admin user ownership and can be started
manually or through the web interface.
"""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import PipelineExecution, User
from app.extensions import db

app = create_app()
with app.app_context():
    # Get admin user
    user = User.query.filter_by(username='admin').first()
    if not user:
        print("Admin user not found!")
        sys.exit(1)
    
    print(f"Using user: {user.username} (id={user.id})")
    
    # Configuration for existing apps re-analysis
    config = {
        'generation': {
            'mode': 'existing',
            'existingApps': [
                {'model_slug': 'anthropic_claude-3-5-haiku', 'app_number': 2},
                {'model_slug': 'anthropic_claude-3-5-haiku', 'app_number': 3}
            ]
        },
        'analysis': {
            'enabled': True,
            'tools': [
                'bandit', 'semgrep', 'safety', 'pip-audit', 
                'eslint', 'npm-audit', 'detect-secrets',
                'owasp-zap', 'aiohttp-test',
                'ai-code-review', 'ai-requirements-compliance'
            ],
            'autoStartContainers': True,
            'stopAfterAnalysis': False,
            'options': {
                'parallel': True,
                'maxConcurrentTasks': 2
            }
        }
    }
    
    # Create pipeline
    pipeline = PipelineExecution(
        user_id=user.id,
        config=config,
        name='Re-analyze fixed apps (app2 & app3)'
    )
    
    db.session.add(pipeline)
    db.session.commit()
    
    print(f"Created pipeline: {pipeline.pipeline_id}")
    print(f"Status: {pipeline.status}, Stage: {pipeline.current_stage}")
