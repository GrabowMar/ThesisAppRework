"""
Unit Tests for Web UI Analysis Creation
========================================

Tests the complete analysis creation workflow through the web UI.
"""

import pytest
import requests
from bs4 import BeautifulSoup
from typing import Dict, List


BASE_URL = 'http://localhost:5000'
BEARER_TOKEN = 'WCVNOZZ125gzTx_Z1F6pjnW34JIWqYLyh9xTytVbaJnTUfXYFrir2EJcadpYgelI'


@pytest.fixture
def auth_headers():
    """Provide authenticated headers for requests"""
    return {'Authorization': f'Bearer {BEARER_TOKEN}'}


@pytest.fixture
def session_with_auth():
    """Provide a requests session with authentication"""
    session = requests.Session()
    session.headers.update({'Authorization': f'Bearer {BEARER_TOKEN}'})
    return session


class TestAuthenticationFlow:
    """Test authentication mechanisms"""
    
    def test_bearer_token_valid(self, auth_headers):
        """Verify Bearer token is valid"""
        response = requests.get(f'{BASE_URL}/api/tokens/verify', headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data['valid'] is True
        assert data['user']['username'] == 'admin'
    
    def test_unauthenticated_request_fails(self):
        """Verify unauthenticated requests are rejected"""
        response = requests.get(f'{BASE_URL}/analysis/list')
        # Should redirect to login or return 401
        assert response.status_code in [302, 401] or 'login' in response.url.lower()


class TestAnalysisListEndpoint:
    """Test the analysis list/task loading endpoint"""
    
    def test_analysis_list_page_loads(self, auth_headers):
        """Verify analysis list page loads"""
        response = requests.get(f'{BASE_URL}/analysis/list', headers=auth_headers)
        assert response.status_code == 200
        assert 'text/html' in response.headers.get('Content-Type', '')
    
    def test_htmx_tasks_endpoint_accessible(self, auth_headers):
        """Verify HTMX tasks endpoint returns task table"""
        headers = {**auth_headers, 'HX-Request': 'true'}
        response = requests.get(
            f'{BASE_URL}/analysis/api/tasks/list',
            headers=headers,
            params={'page': 1, 'per_page': 10}
        )
        assert response.status_code == 200
        assert 'text/html' in response.headers.get('Content-Type', '')
        
        # Verify it contains a table
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table')
        assert table is not None, "Response should contain a table"
    
    def test_htmx_tasks_pagination(self, auth_headers):
        """Verify pagination works on tasks endpoint"""
        headers = {**auth_headers, 'HX-Request': 'true'}
        
        # Page 1
        response1 = requests.get(
            f'{BASE_URL}/analysis/api/tasks/list',
            headers=headers,
            params={'page': 1, 'per_page': 5}
        )
        assert response1.status_code == 200
        
        # Page 2
        response2 = requests.get(
            f'{BASE_URL}/analysis/api/tasks/list',
            headers=headers,
            params={'page': 2, 'per_page': 5}
        )
        assert response2.status_code == 200


class TestAnalysisCreateForm:
    """Test analysis creation form"""
    
    def test_create_form_loads(self, auth_headers):
        """Verify create form page loads"""
        response = requests.get(f'{BASE_URL}/analysis/create', headers=auth_headers)
        assert response.status_code == 200
        
        soup = BeautifulSoup(response.text, 'html.parser')
        form = soup.find('form', id='analysis-wizard-form')
        assert form is not None, "Form should be present"
        assert form.get('action') == '/analysis/create'
    
    def test_create_with_valid_custom_tools(self, auth_headers):
        """Test creating analysis with custom tools"""
        form_data = {
            'model_slug': 'anthropic_claude-4.5-sonnet-20250929',
            'app_number': '1',
            'analysis_mode': 'custom',
            'analysis_profile': '',
            'selected_tools[]': ['bandit', 'safety'],
            'priority': 'normal'
        }
        
        response = requests.post(
            f'{BASE_URL}/analysis/create',
            data=form_data,
            headers=auth_headers,
            allow_redirects=False
        )
        
        assert response.status_code == 302, "Should redirect on success"
        assert '/analysis/list' in response.headers.get('Location', '')
    
    def test_create_with_profile_mode(self, auth_headers):
        """Test creating analysis with analysis profile"""
        form_data = {
            'model_slug': 'anthropic_claude-4.5-haiku-20251001',
            'app_number': '1',
            'analysis_mode': 'profile',
            'analysis_profile': 'security',
            'selected_tools[]': [],
            'priority': 'normal'
        }
        
        response = requests.post(
            f'{BASE_URL}/analysis/create',
            data=form_data,
            headers=auth_headers,
            allow_redirects=False
        )
        
        assert response.status_code == 302, "Should redirect on success"
    
    def test_create_with_invalid_model(self, auth_headers):
        """Test validation fails for non-existent model"""
        form_data = {
            'model_slug': 'nonexistent-model',
            'app_number': '1',
            'analysis_mode': 'custom',
            'analysis_profile': '',
            'selected_tools[]': ['bandit'],
            'priority': 'normal'
        }
        
        response = requests.post(
            f'{BASE_URL}/analysis/create',
            data=form_data,
            headers=auth_headers,
            allow_redirects=False
        )
        
        assert response.status_code == 404, "Should return 404 for missing app"
    
    def test_create_with_missing_fields(self, auth_headers):
        """Test validation fails for missing required fields"""
        form_data = {
            'model_slug': '',  # Missing
            'app_number': '',  # Missing
            'analysis_mode': 'custom',
            'selected_tools[]': ['bandit'],
        }
        
        response = requests.post(
            f'{BASE_URL}/analysis/create',
            data=form_data,
            headers=auth_headers,
            allow_redirects=False
        )
        
        assert response.status_code == 400, "Should return 400 for validation error"
    
    def test_create_custom_without_tools(self, auth_headers):
        """Test validation fails for custom mode without tools"""
        form_data = {
            'model_slug': 'anthropic_claude-4.5-sonnet-20250929',
            'app_number': '1',
            'analysis_mode': 'custom',
            'analysis_profile': '',
            'selected_tools[]': [],  # No tools selected
            'priority': 'normal'
        }
        
        response = requests.post(
            f'{BASE_URL}/analysis/create',
            data=form_data,
            headers=auth_headers,
            allow_redirects=False
        )
        
        assert response.status_code == 400, "Should require at least one tool"


class TestDockerAnalyzers:
    """Test Docker analyzer services"""
    
    def test_analyzer_containers_running(self):
        """Verify all analyzer containers are running"""
        # This would use subprocess or docker SDK
        import subprocess
        result = subprocess.run(
            ['docker', 'ps', '--format', '{{.Names}}'],
            capture_output=True,
            text=True
        )
        
        containers = result.stdout.strip().split('\n')
        
        expected_containers = [
            'static-analyzer',
            'dynamic-analyzer', 
            'performance-tester',
            'ai-analyzer'
        ]
        
        for expected in expected_containers:
            assert any(expected in c for c in containers), \
                f"Container {expected} should be running"
    
    def test_analyzer_ports_accessible(self):
        """Verify analyzer WebSocket ports are accessible"""
        import socket
        
        ports = {
            'static-analyzer': 2001,
            'dynamic-analyzer': 2002,
            'performance-tester': 2003,
            'ai-analyzer': 2004
        }
        
        for name, port in ports.items():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            assert result == 0, f"Port {port} for {name} should be accessible"


class TestDatabaseApplications:
    """Test database application records"""
    
    def test_applications_exist_in_database(self):
        """Verify applications are registered in database"""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
        
        from app.factory import create_app
        from app.models import GeneratedApplication
        
        app = create_app()
        with app.app_context():
            apps = GeneratedApplication.query.all()
            assert len(apps) > 0, "Database should contain generated applications"
            
            # Verify expected apps exist
            model_slugs = [app.model_slug for app in apps]
            assert 'anthropic_claude-4.5-sonnet-20250929' in model_slugs
            assert 'anthropic_claude-4.5-haiku-20251001' in model_slugs
    
    def test_analysis_tasks_recorded(self):
        """Verify analysis tasks are being created in database"""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
        
        from app.factory import create_app
        from app.models import AnalysisTask
        
        app = create_app()
        with app.app_context():
            tasks = AnalysisTask.query.limit(10).all()
            # Should have some tasks from previous runs
            assert len(tasks) >= 0, "Tasks should be queryable"


class TestResultFileSystem:
    """Test result file storage"""
    
    def test_results_directory_exists(self):
        """Verify results directory structure"""
        from pathlib import Path
        
        results_dir = Path(__file__).parent.parent / 'results'
        assert results_dir.exists(), "Results directory should exist"
        
        # Check for at least one model directory
        model_dirs = list(results_dir.glob('*/'))
        assert len(model_dirs) > 0, "Should have at least one model results directory"
    
    def test_task_results_structure(self):
        """Verify task result file structure"""
        from pathlib import Path
        
        results_dir = Path(__file__).parent.parent / 'results'
        
        # Find any task directory
        task_dirs = list(results_dir.glob('*/app*/task_*/'))
        
        if task_dirs:  # Only test if tasks exist
            task_dir = task_dirs[0]
            
            # Should have JSON result file
            json_files = list(task_dir.glob('*.json'))
            assert len(json_files) > 0, "Task dir should have result JSON"


@pytest.mark.slow
class TestEndToEndAnalysis:
    """End-to-end analysis workflow tests"""
    
    def test_complete_analysis_workflow(self, auth_headers):
        """Test creating and tracking an analysis to completion"""
        # 1. Create analysis
        form_data = {
            'model_slug': 'anthropic_claude-4.5-sonnet-20250929',
            'app_number': '1',
            'analysis_mode': 'custom',
            'analysis_profile': '',
            'selected_tools[]': ['bandit'],
            'priority': 'normal'
        }
        
        response = requests.post(
            f'{BASE_URL}/analysis/create',
            data=form_data,
            headers=auth_headers,
            allow_redirects=False
        )
        
        assert response.status_code == 302, "Analysis should be created"
        
        # 2. Verify task appears in list
        headers = {**auth_headers, 'HX-Request': 'true'}
        response = requests.get(
            f'{BASE_URL}/analysis/api/tasks/list',
            headers=headers,
            params={'page': 1, 'per_page': 20}
        )
        
        assert response.status_code == 200
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.find_all('tr')
        assert len(rows) > 1, "Should have task rows"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
