"""
Tests for database-backed task detail page functionality.
"""
import pytest
from datetime import datetime, timezone

from app.models import AnalysisTask, AnalysisResult
from app.constants import AnalysisStatus, SeverityLevel
from app.extensions import db


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def authenticated_client(app, client):
    """Create an authenticated test client."""
    from app.models import User
    
    with app.app_context():
        # Create test user
        user = User(username='testuser', email='test@example.com')
        user.set_password('testpass')
        db.session.add(user)
        db.session.commit()
        
        # Login
        client.post('/auth/login', data={
            'username': 'testuser',
            'password': 'testpass'
        }, follow_redirects=True)
        
        yield client


@pytest.fixture
def sample_task(app):
    """Create a sample analysis task for testing."""
    with app.app_context():
        task = AnalysisTask(
            task_id='test-task-12345',
            target_model='openai_gpt-4',
            target_app_number=1,
            status=AnalysisStatus.COMPLETED,
            created_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            issues_found=3
        )
        db.session.add(task)
        db.session.commit()
        
        yield task
        
        # Cleanup
        db.session.delete(task)
        db.session.commit()


@pytest.fixture
def sample_results(app, sample_task):
    """Create sample analysis results for testing."""
    with app.app_context():
        results = [
            AnalysisResult(
                task_id=sample_task.task_id,
                service_name='static-analyzer',
                tool_name='bandit',
                severity=SeverityLevel.HIGH,
                message='Hardcoded password detected',
                file_path='src/config.py',
                line_number=42,
                category='security'
            ),
            AnalysisResult(
                task_id=sample_task.task_id,
                service_name='static-analyzer',
                tool_name='eslint',
                severity=SeverityLevel.MEDIUM,
                message='Unused variable',
                file_path='src/app.js',
                line_number=15,
                category='code_quality'
            ),
            AnalysisResult(
                task_id=sample_task.task_id,
                service_name='static-analyzer',
                tool_name='bandit',
                severity=SeverityLevel.CRITICAL,
                message='SQL injection vulnerability',
                file_path='src/database.py',
                line_number=78,
                category='security'
            ),
        ]
        
        for result in results:
            db.session.add(result)
        db.session.commit()
        
        yield results
        
        # Cleanup
        for result in results:
            db.session.delete(result)
        db.session.commit()


class TestTaskDetailRoute:
    """Tests for the task detail route."""
    
    def test_task_detail_requires_auth(self, client, sample_task):
        """Test that task detail requires authentication."""
        response = client.get(f'/analysis/tasks/{sample_task.task_id}')
        # Should redirect to login
        assert response.status_code == 302
        assert '/auth/login' in response.location
    
    def test_task_detail_loads_successfully(self, authenticated_client, sample_task, sample_results):
        """Test that task detail page loads with valid task."""
        response = authenticated_client.get(f'/analysis/tasks/{sample_task.task_id}')
        assert response.status_code == 200
        assert b'test-task-12345' in response.data
        assert b'openai_gpt-4' in response.data
    
    def test_task_detail_404_for_missing_task(self, authenticated_client):
        """Test that missing task returns 404."""
        response = authenticated_client.get('/analysis/tasks/nonexistent-task')
        assert response.status_code == 404
    
    def test_task_detail_displays_findings(self, authenticated_client, sample_task, sample_results):
        """Test that findings are displayed correctly."""
        response = authenticated_client.get(f'/analysis/tasks/{sample_task.task_id}')
        assert response.status_code == 200
        
        # Check for findings content
        assert b'Hardcoded password detected' in response.data
        assert b'Unused variable' in response.data
        assert b'SQL injection vulnerability' in response.data
        
        # Check for tool names
        assert b'bandit' in response.data
        assert b'eslint' in response.data
        
        # Check for file paths
        assert b'src/config.py' in response.data
        assert b'src/app.js' in response.data
        assert b'src/database.py' in response.data
    
    def test_task_detail_severity_breakdown(self, authenticated_client, sample_task, sample_results):
        """Test that severity breakdown is calculated correctly."""
        response = authenticated_client.get(f'/analysis/tasks/{sample_task.task_id}')
        assert response.status_code == 200
        
        # Should show severity counts
        data = response.data.decode('utf-8')
        assert 'critical' in data.lower() or 'Critical' in data
        assert 'high' in data.lower() or 'High' in data
        assert 'medium' in data.lower() or 'Medium' in data
    
    def test_task_detail_tools_used(self, authenticated_client, sample_task, sample_results):
        """Test that tools used are displayed."""
        response = authenticated_client.get(f'/analysis/tasks/{sample_task.task_id}')
        assert response.status_code == 200
        
        # Check that both tools are mentioned
        assert b'bandit' in response.data
        assert b'eslint' in response.data
    
    def test_task_detail_with_no_findings(self, authenticated_client, app):
        """Test task detail page with no findings."""
        with app.app_context():
            task = AnalysisTask(
                task_id='test-empty-task',
                target_model='test_model',
                target_app_number=1,
                status=AnalysisStatus.COMPLETED,
                created_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                issues_found=0
            )
            db.session.add(task)
            db.session.commit()
            
            response = authenticated_client.get(f'/analysis/tasks/{task.task_id}')
            assert response.status_code == 200
            
            # Should show empty state
            assert b'No Findings' in response.data or b'no issues' in response.data.lower()
            
            # Cleanup
            db.session.delete(task)
            db.session.commit()
    
    def test_task_detail_findings_pagination(self, authenticated_client, sample_task, sample_results):
        """Test that findings pagination works."""
        # Test with limit
        response = authenticated_client.get(f'/analysis/tasks/{sample_task.task_id}?findings=1')
        assert response.status_code == 200
        
        # Should show pagination indicator
        data = response.data.decode('utf-8')
        assert 'Showing first 1' in data or 'first 1' in data.lower()
    
    def test_task_detail_failed_task_shows_error(self, authenticated_client, app):
        """Test that failed tasks display error message."""
        with app.app_context():
            task = AnalysisTask(
                task_id='test-failed-task',
                target_model='test_model',
                target_app_number=1,
                status=AnalysisStatus.FAILED,
                created_at=datetime.now(timezone.utc),
                error_message='Analysis failed due to timeout'
            )
            db.session.add(task)
            db.session.commit()
            
            response = authenticated_client.get(f'/analysis/tasks/{task.task_id}')
            assert response.status_code == 200
            
            # Should show error message
            assert b'Analysis failed due to timeout' in response.data
            assert b'Task Failed' in response.data or b'failed' in response.data.lower()
            
            # Cleanup
            db.session.delete(task)
            db.session.commit()


class TestTasksTableUpdate:
    """Tests for tasks table updates."""
    
    def test_tasks_table_links_to_task_detail(self, authenticated_client, sample_task):
        """Test that completed tasks link to task detail page."""
        response = authenticated_client.get('/analysis/api/tasks/list')
        assert response.status_code == 200
        
        # Should contain link to task detail
        assert f'/analysis/tasks/{sample_task.task_id}'.encode() in response.data


class TestTaskDetailIntegration:
    """Integration tests for task detail page."""
    
    def test_full_task_detail_workflow(self, authenticated_client, app):
        """Test complete workflow from task creation to viewing details."""
        with app.app_context():
            # Create task
            task = AnalysisTask(
                task_id='integration-test-task',
                target_model='anthropic_claude',
                target_app_number=5,
                status=AnalysisStatus.COMPLETED,
                created_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                issues_found=2
            )
            db.session.add(task)
            db.session.commit()
            
            # Create results
            result1 = AnalysisResult(
                task_id=task.task_id,
                service_name='static-analyzer',
                tool_name='pylint',
                severity=SeverityLevel.HIGH,
                message='Missing docstring',
                file_path='src/main.py',
                line_number=10
            )
            result2 = AnalysisResult(
                task_id=task.task_id,
                service_name='static-analyzer',
                tool_name='pylint',
                severity=SeverityLevel.LOW,
                message='Line too long',
                file_path='src/main.py',
                line_number=25
            )
            db.session.add(result1)
            db.session.add(result2)
            db.session.commit()
            
            # View task detail
            response = authenticated_client.get(f'/analysis/tasks/{task.task_id}')
            assert response.status_code == 200
            
            # Verify all elements present
            assert b'anthropic_claude' in response.data
            assert b'Missing docstring' in response.data
            assert b'Line too long' in response.data
            assert b'pylint' in response.data
            assert b'src/main.py' in response.data
            
            # Cleanup
            db.session.delete(result1)
            db.session.delete(result2)
            db.session.delete(task)
            db.session.commit()
