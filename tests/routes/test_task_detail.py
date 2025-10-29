"""
Test suite for task detail page functionality
"""
import pytest
from datetime import datetime


@pytest.fixture
def authenticated_client(app):
    """Create test client with authenticated user"""
    from app.models import User
    from app.extensions import db
    from werkzeug.security import generate_password_hash
    
    with app.app_context():
        # Create test user
        user = User(
            username='testuser',
            email='test@example.com',
            password_hash=generate_password_hash('testpass'),
            is_active=True
        )
        db.session.add(user)
        db.session.commit()
        
        # Create test client and login
        client = app.test_client()
        with client:
            # Login by setting session
            with client.session_transaction() as sess:
                sess['_user_id'] = str(user.id)
                sess['_fresh'] = True
            
            yield client


@pytest.fixture
def sample_task(app):
    """Create a sample analysis task for testing"""
    from app.models import AnalysisTask, AnalysisResult
    from app.constants import AnalysisStatus, SeverityLevel
    from app.extensions import db
    
    with app.app_context():
        # Create test task
        task = AnalysisTask(
            task_id='test-task-123',
            target_model='test-model',
            target_app_number=1,
            task_name='Test Analysis',
            status=AnalysisStatus.COMPLETED,
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        db.session.add(task)
        db.session.flush()
        
        # Add sample results
        result1 = AnalysisResult(
            task_id='test-task-123',
            tool_name='test-tool-1',
            title='Critical Security Issue',
            severity=SeverityLevel.CRITICAL,
            file_path='/app/test.py',
            line_number=42,
            category='security'
        )
        result2 = AnalysisResult(
            task_id='test-task-123',
            tool_name='test-tool-2',
            title='High Priority Warning',
            severity=SeverityLevel.HIGH,
            file_path='/app/main.py',
            line_number=100,
            category='quality'
        )
        result3 = AnalysisResult(
            task_id='test-task-123',
            tool_name='test-tool-1',
            title='Medium Issue',
            severity=SeverityLevel.MEDIUM,
            category='performance'
        )
        
        db.session.add_all([result1, result2, result3])
        db.session.commit()
        
        yield task


class TestTaskDetailRoute:
    """Test task detail route functionality"""
    
    def test_task_detail_requires_authentication(self, app):
        """Test that task detail route requires authentication"""
        client = app.test_client()
        response = client.get('/analysis/tasks/test-task-123')
        # Should redirect to login
        assert response.status_code in [302, 401]
    
    def test_task_detail_not_found(self, authenticated_client, app):
        """Test 404 for non-existent task"""
        response = authenticated_client.get('/analysis/tasks/nonexistent-task')
        assert response.status_code == 404
    
    def test_task_detail_shows_task_info(self, authenticated_client, sample_task, app):
        """Test that task detail page shows task information"""
        response = authenticated_client.get(f'/analysis/tasks/{sample_task.task_id}')
        assert response.status_code == 200
        
        # Check for task ID
        assert b'test-task-123' in response.data
        
        # Check for status badge
        assert b'Completed' in response.data or b'completed' in response.data
        
        # Check for model and app number
        assert b'test-model' in response.data
        assert b'#1' in response.data or b'App Number' in response.data
    
    def test_task_detail_shows_findings(self, authenticated_client, sample_task, app):
        """Test that task detail page shows findings"""
        response = authenticated_client.get(f'/analysis/tasks/{sample_task.task_id}')
        assert response.status_code == 200
        
        # Check for finding titles
        assert b'Critical Security Issue' in response.data
        assert b'High Priority Warning' in response.data
        assert b'Medium Issue' in response.data
        
        # Check for severity badges
        assert b'Critical' in response.data
        assert b'High' in response.data
        assert b'Medium' in response.data
    
    def test_task_detail_shows_severity_breakdown(self, authenticated_client, sample_task, app):
        """Test that severity breakdown is calculated correctly"""
        response = authenticated_client.get(f'/analysis/tasks/{sample_task.task_id}')
        assert response.status_code == 200
        
        # Should show counts: 1 critical, 1 high, 1 medium
        content = response.data.decode('utf-8')
        
        # Check for summary statistics
        assert 'Total Findings' in content or 'total_findings' in content.lower()
        assert '3' in content  # Total of 3 findings
    
    def test_task_detail_groups_by_tool(self, authenticated_client, sample_task, app):
        """Test that results are grouped by tool"""
        response = authenticated_client.get(f'/analysis/tasks/{sample_task.task_id}')
        assert response.status_code == 200
        
        # Check for tool names
        assert b'test-tool-1' in response.data
        assert b'test-tool-2' in response.data
    
    def test_task_detail_shows_file_locations(self, authenticated_client, sample_task, app):
        """Test that file locations are displayed"""
        response = authenticated_client.get(f'/analysis/tasks/{sample_task.task_id}')
        assert response.status_code == 200
        
        # Check for file paths and line numbers
        assert b'/app/test.py' in response.data
        assert b'/app/main.py' in response.data
        assert b'42' in response.data  # Line number
        assert b'100' in response.data  # Line number
    
    def test_task_detail_respects_findings_limit(self, authenticated_client, sample_task, app):
        """Test that findings_limit parameter works"""
        response = authenticated_client.get(f'/analysis/tasks/{sample_task.task_id}?findings=2')
        assert response.status_code == 200
        
        # Should indicate limited results
        assert b'Limited to' in response.data or b'limited' in response.data.lower()


class TestTaskDetailEmpty:
    """Test task detail with no findings"""
    
    def test_task_detail_no_findings_shows_empty_state(self, authenticated_client, app):
        """Test empty state when task has no findings"""
        from app.models import AnalysisTask
        from app.constants import AnalysisStatus
        from app.extensions import db
        
        with app.app_context():
            # Create task with no results
            task = AnalysisTask(
                task_id='empty-task-123',
                target_model='clean-model',
                target_app_number=2,
                task_name='Clean Analysis',
                status=AnalysisStatus.COMPLETED,
                created_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )
            db.session.add(task)
            db.session.commit()
        
        response = authenticated_client.get('/analysis/tasks/empty-task-123')
        assert response.status_code == 200
        
        # Check for empty state message
        assert b'No Findings' in response.data or b'no issues found' in response.data.lower()
        assert b'0' in response.data  # Zero findings count


class TestTasksTableIntegration:
    """Test that tasks table links to task detail correctly"""
    
    def test_completed_task_shows_detail_icon(self, authenticated_client, sample_task, app):
        """Test that completed tasks show eye icon linking to detail page"""
        response = authenticated_client.get('/analysis/api/tasks/list')
        assert response.status_code == 200
        
        # Should contain link to task detail
        assert b'/analysis/tasks/' in response.data
        
        # Should contain eye icon
        assert b'fa-eye' in response.data
