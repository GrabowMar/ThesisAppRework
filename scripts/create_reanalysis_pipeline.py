"""Create a new pipeline to re-analyze fixed apps."""
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
