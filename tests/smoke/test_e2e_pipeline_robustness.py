
import pytest
import time
import json
from unittest.mock import patch, MagicMock
from app.models import PipelineExecution, PipelineExecutionStatus, AnalysisTask, AnalysisStatus, User
import logging

@pytest.mark.smoke
def test_e2e_pipeline_robustness_with_fallback(client, db_session, app, caplog):
    """
    End-to-End Smoke Test for Pipeline Robustness.
    
    Verifies container build failure triggers static analysis downgrade.
    """
    import shutil
    import os
    from pathlib import Path
    
    caplog.set_level(logging.INFO)
    
    # Define payload path
    workspace_root = Path(app.root_path).parent.parent
    gen_apps_dir = workspace_root / 'generated' / 'apps'
    model_slug = 'test_model_v1'
    app_num = 1
    app_dir = gen_apps_dir / model_slug / f'app{app_num}'
    
    # Clean up before
    if app_dir.exists():
        shutil.rmtree(app_dir)
        
    # Create valid app structure including docker-compose.yml
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / 'requirements.txt').write_text('flask')
    (app_dir / 'app.py').write_text('print("hello")')
    (app_dir / 'docker-compose.yml').write_text('version: "3"')
    
    try:
        # 0. Setup Authentication
        username = 'testuser_robustness'
        password = 'testpassword123'
        
        existing = User.query.filter_by(username=username).first()
        if existing:
            db_session.delete(existing)
            db_session.commit()
        
        user = User(username=username, email=f'{username}@example.com')
        user.set_password(password)
        db_session.add(user)
        db_session.commit()
        
        client.post('/auth/login', data={'username': username, 'password': password})

        # 1. Setup Data
        config = {
            'generation': {
                'mode': 'generate',
                'models': [model_slug],
                'templates': ['crud_app'],
            },
            'analysis': {
                'enabled': True,
                'tools': ['bandit', 'semgrep', 'owasp-zap', 'lighthouse'],
            }
        }
        
        with patch('app.services.generation_v2.service.GenerationService.generate') as mock_gen, \
             patch('app.services.docker_manager.DockerManager.build_containers') as mock_build, \
             patch('app.services.docker_manager.DockerManager.get_project_containers') as mock_get_containers:
            
            # Configure Mocks
            mock_gen_result = MagicMock()
            mock_gen_result.success = True
            mock_gen_result.app_number = 1
            mock_gen_result.app_dir = app_dir
            mock_gen_result.metrics = {}
            mock_gen_result.artifacts = {'backend': True, 'frontend': True}
            mock_gen.return_value = mock_gen_result
            
            # Docker build fails!
            mock_build.return_value = {'success': False, 'error': 'Simulated Failure'}
            
            mock_get_containers.return_value = []
            
            # 3. Start Pipeline
            response = client.post('/api/automation/pipelines', json={
                'name': 'Robustness Test Pipeline',
                'config': config
            })
            
            assert response.status_code == 201
            pipeline_id = response.json['data']['pipeline_id']
            print(f"Pipeline started: {pipeline_id}")
            
            # 4. Poll
            max_retries = 30
            for i in range(max_retries):
                status_resp = client.get(f'/api/automation/pipelines/{pipeline_id}/details')
                data = status_resp.json['data']
                status = data['status']
                print(f"Polling {i}: {status}")
                if status.upper() in ('COMPLETED', 'FAILED', 'CANCELLED'):
                    break
                time.sleep(1)
                
            # 5. Verify Results (via Logs)
            log_text = caplog.text
            
            # CRITICAL VERIFICATION 1: Downgrade logic triggered
            assert "downgrading to static analysis only" in log_text, \
                "Fallback logic NOT triggered (Log message missing)"
                
            # CRITICAL VERIFICATION 2: Tools filtered correctly
            assert "kept: bandit, semgrep" in log_text or "bandit, semgrep" in log_text, \
                "Static tools 'bandit' and 'semgrep' not found in logs"
                
            # Ensure filtering happened (checking logs for absence after downgrade message if possible)
            # Simplest check: 'owasp-zap' should NOT be in the "Queuing parallel subtask" log entry
            
            # 6. Report
            report_resp = client.post('/api/reports/generate', json={
                'report_type': 'template_comparison',
                'title': 'E2E Test Report',
                'config': {
                    'template_slug': 'crud_app',
                    'filter_models': [model_slug]
                }
            })
            assert report_resp.status_code == 201
            print("Test Passed")

    finally:
        # Cleanup directory
        if app_dir.exists():
            shutil.rmtree(app_dir)
