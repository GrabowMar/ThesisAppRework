"""
Comprehensive Test Suite for Batch Dashboard System
Tests all components: models, services, routes, and integration

This test suite verifies the complete batch analysis system including:
- Database models and relationships
- Service layer functionality
- API endpoints and web routes
- Error handling and edge cases
- Performance and concurrent operations
"""

import pytest
import tempfile
import threading
import time
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import our application components
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from app import create_app
from extensions import db
from models import (
    BatchJob, BatchTask, BatchWorker, GeneratedApplication,
    JobStatus, TaskStatus, JobPriority, AnalysisType
)
from batch_service import (
    BatchJobManager, BatchTaskRunner, BatchWorkerPool, BatchProgressTracker
)


class TestDatabaseModels:
    """Test enhanced database models for batch processing"""
    
    @pytest.fixture
    def app(self):
        """Create test Flask application"""
        app = create_app()
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        with app.app_context():
            db.create_all()
            yield app
            db.drop_all()
    
    @pytest.fixture
    def db_session(self, app):
        """Provide database session for tests"""
        with app.app_context():
            yield db.session
    
    def test_batch_job_creation(self, db_session):
        """Test BatchJob model creation and validation"""
        job = BatchJob(
            name="Test Security Analysis",
            description="Testing security analysis batch job",
            priority=JobPriority.HIGH,
            analysis_types=[AnalysisType.SECURITY_ANALYSIS, AnalysisType.ZAP_SCAN],
            models_to_analyze=["anthropic_claude-3.7-sonnet", "test_model"],
            app_range="1-5",
            created_by="test_user"
        )
        
        db_session.add(job)
        db_session.commit()
        
        # Test basic properties
        assert job.id is not None
        assert job.name == "Test Security Analysis"
        assert job.status == JobStatus.PENDING
        assert job.priority == JobPriority.HIGH
        assert len(job.analysis_types) == 2
        assert AnalysisType.SECURITY_ANALYSIS in job.analysis_types
        assert len(job.models_to_analyze) == 2
        assert job.created_at is not None
        
        # Test calculated properties
        assert job.total_tasks == 0  # No tasks created yet
        assert job.progress_percentage == 0.0
        assert job.can_be_cancelled is True
        assert job.can_be_restarted is False
    
    def test_batch_task_creation(self, db_session):
        """Test BatchTask model creation and relationships"""
        # Create parent job
        job = BatchJob(
            name="Test Job",
            analysis_types=[AnalysisType.SECURITY_ANALYSIS],
            models_to_analyze=["test_model"],
            app_range="1"
        )
        db_session.add(job)
        db_session.commit()
        
        # Create task
        task = BatchTask(
            job_id=job.id,
            task_type=AnalysisType.SECURITY_ANALYSIS,
            model_name="test_model",
            app_number=1,
            task_config={"timeout": 300, "tools": ["bandit", "safety"]}
        )
        db_session.add(task)
        db_session.commit()
        
        # Test properties
        assert task.id is not None
        assert task.job_id == job.id
        assert task.status == TaskStatus.PENDING
        assert task.task_type == AnalysisType.SECURITY_ANALYSIS
        assert task.model_name == "test_model"
        assert task.app_number == 1
        assert task.task_config["timeout"] == 300
        assert task.can_be_retried is True
        
        # Test relationships
        assert task.job == job
        assert task in job.tasks
    
    def test_batch_worker_lifecycle(self, db_session):
        """Test BatchWorker model lifecycle"""
        worker = BatchWorker(
            worker_id="worker_001",
            status="active",
            worker_type="analysis",
            max_concurrent_tasks=3
        )
        db_session.add(worker)
        db_session.commit()
        
        # Test initial state
        assert worker.id is not None
        assert worker.worker_id == "worker_001"
        assert worker.status == "active"
        assert worker.current_task_count == 0
        assert worker.total_tasks_completed == 0
        assert worker.is_available is True
        
        # Simulate task assignment
        worker.current_task_count = 2
        assert worker.is_available is True  # Still under max
        
        worker.current_task_count = 3
        assert worker.is_available is False  # At capacity
    
    def test_job_progress_calculation(self, db_session):
        """Test job progress calculation with multiple tasks"""
        job = BatchJob(
            name="Progress Test Job",
            analysis_types=[AnalysisType.SECURITY_ANALYSIS],
            models_to_analyze=["test_model"],
            app_range="1-3"
        )
        db_session.add(job)
        db_session.commit()
        
        # Create tasks
        tasks = []
        for i in range(1, 4):
            task = BatchTask(
                job_id=job.id,
                task_type=AnalysisType.SECURITY_ANALYSIS,
                model_name="test_model",
                app_number=i
            )
            tasks.append(task)
            db_session.add(task)
        
        db_session.commit()
        
        # Test initial progress
        assert job.total_tasks == 3
        assert job.progress_percentage == 0.0
        
        # Complete one task
        tasks[0].status = TaskStatus.COMPLETED
        db_session.commit()
        
        # Refresh and test progress
        db_session.refresh(job)
        assert job.progress_percentage == pytest.approx(33.33, rel=1e-2)
        
        # Complete all tasks
        for task in tasks:
            task.status = TaskStatus.COMPLETED
        db_session.commit()
        
        db_session.refresh(job)
        assert job.progress_percentage == 100.0
    
    def test_model_validation(self, db_session):
        """Test model validation rules"""
        # Test job name length validation
        with pytest.raises(Exception):  # Should raise validation error
            job = BatchJob(
                name="x" * 201,  # Exceeds max length
                analysis_types=[AnalysisType.SECURITY_ANALYSIS],
                models_to_analyze=["test_model"],
                app_range="1"
            )
            db_session.add(job)
            db_session.commit()
    
    def test_json_field_operations(self, db_session):
        """Test JSON field operations for complex data"""
        job = BatchJob(
            name="JSON Test Job",
            analysis_types=[AnalysisType.SECURITY_ANALYSIS],
            models_to_analyze=["test_model"],
            app_range="1",
            job_config={
                "timeout": 600,
                "retry_policy": {"max_retries": 3, "backoff": "exponential"},
                "notifications": {"email": True, "webhook": False}
            }
        )
        db_session.add(job)
        db_session.commit()
        
        # Test JSON retrieval
        assert job.job_config["timeout"] == 600
        assert job.job_config["retry_policy"]["max_retries"] == 3
        assert job.job_config["notifications"]["email"] is True
        
        # Test JSON modification
        job.job_config["timeout"] = 900
        db_session.commit()
        
        db_session.refresh(job)
        assert job.job_config["timeout"] == 900


class TestBatchService:
    """Test batch service layer functionality"""
    
    @pytest.fixture
    def app(self):
        """Create test Flask application"""
        app = create_app()
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        with app.app_context():
            db.create_all()
            yield app
            db.drop_all()
    
    @pytest.fixture
    def batch_manager(self, app):
        """Create BatchJobManager instance"""
        with app.app_context():
            manager = BatchJobManager()
            yield manager
            manager.cleanup()
    
    def test_job_creation_service(self, batch_manager):
        """Test job creation through service layer"""
        job_data = {
            "name": "Service Test Job",
            "description": "Testing job creation via service",
            "analysis_types": ["security_analysis", "zap_scan"],
            "models_to_analyze": ["test_model"],
            "app_range": "1-3",
            "priority": "high"
        }
        
        job = batch_manager.create_job(**job_data)
        
        assert job is not None
        assert job.name == "Service Test Job"
        assert len(job.analysis_types) == 2
        assert job.priority == JobPriority.HIGH
        assert job.status == JobStatus.PENDING
    
    def test_task_generation(self, batch_manager):
        """Test automatic task generation"""
        job_data = {
            "name": "Task Generation Test",
            "analysis_types": ["security_analysis"],
            "models_to_analyze": ["model1", "model2"],
            "app_range": "1-2"
        }
        
        job = batch_manager.create_job(**job_data)
        tasks = batch_manager.generate_tasks(job.id)
        
        # Should create 4 tasks (2 models × 2 apps × 1 analysis type)
        assert len(tasks) == 4
        
        # Verify task properties
        for task in tasks:
            assert task.job_id == job.id
            assert task.task_type == AnalysisType.SECURITY_ANALYSIS
            assert task.model_name in ["model1", "model2"]
            assert task.app_number in [1, 2]
            assert task.status == TaskStatus.PENDING
    
    def test_app_range_parsing(self, batch_manager):
        """Test various app range formats"""
        test_cases = [
            ("1-5", [1, 2, 3, 4, 5]),
            ("1,3,5", [1, 3, 5]),
            ("10", [10]),
            ("1-3,7,9-10", [1, 2, 3, 7, 9, 10])
        ]
        
        for app_range, expected in test_cases:
            result = batch_manager._parse_app_range(app_range)
            assert sorted(result) == sorted(expected), f"Failed for range: {app_range}"
    
    @patch('batch_service.SecurityAnalysisService')
    @patch('batch_service.ZapService')
    def test_task_execution(self, mock_zap, mock_security, batch_manager):
        """Test task execution with mocked services"""
        # Setup mocks
        mock_security.return_value.run_security_analysis.return_value = {
            "status": "completed",
            "results": {"vulnerabilities": 0}
        }
        
        # Create job and tasks
        job = batch_manager.create_job(
            name="Execution Test",
            analysis_types=["security_analysis"],
            models_to_analyze=["test_model"],
            app_range="1"
        )
        tasks = batch_manager.generate_tasks(job.id)
        
        # Create task runner
        runner = BatchTaskRunner()
        
        # Execute task
        task = tasks[0]
        result = runner.execute_task(task.id)
        
        assert result["status"] == "completed"
        mock_security.return_value.run_security_analysis.assert_called_once()
    
    def test_worker_pool_management(self, batch_manager):
        """Test worker pool lifecycle management"""
        pool = BatchWorkerPool(max_workers=3)
        
        # Test initial state
        assert pool.max_workers == 3
        assert pool.active_workers == 0
        assert pool.is_healthy() is True
        
        # Start workers
        pool.start_workers()
        assert pool.active_workers > 0
        
        # Test worker assignment
        assert pool.can_accept_task() is True
        
        # Cleanup
        pool.shutdown()
        assert pool.active_workers == 0
    
    def test_progress_tracking(self, batch_manager):
        """Test real-time progress tracking"""
        # Create job with tasks
        job = batch_manager.create_job(
            name="Progress Test",
            analysis_types=["security_analysis"],
            models_to_analyze=["test_model"],
            app_range="1-5"
        )
        tasks = batch_manager.generate_tasks(job.id)
        
        tracker = BatchProgressTracker()
        
        # Test initial progress
        progress = tracker.get_job_progress(job.id)
        assert progress["total_tasks"] == 5
        assert progress["completed_tasks"] == 0
        assert progress["progress_percentage"] == 0.0
        
        # Simulate task completion
        tasks[0].status = TaskStatus.COMPLETED
        db.session.commit()
        
        progress = tracker.get_job_progress(job.id)
        assert progress["completed_tasks"] == 1
        assert progress["progress_percentage"] == 20.0
    
    def test_concurrent_job_execution(self, batch_manager):
        """Test concurrent execution of multiple jobs"""
        jobs = []
        
        # Create multiple jobs
        for i in range(3):
            job = batch_manager.create_job(
                name=f"Concurrent Job {i}",
                analysis_types=["security_analysis"],
                models_to_analyze=["test_model"],
                app_range="1-2"
            )
            jobs.append(job)
        
        # Start all jobs concurrently
        threads = []
        for job in jobs:
            thread = threading.Thread(
                target=batch_manager.start_job,
                args=(job.id,)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for threads to start
        time.sleep(0.1)
        
        # Verify all jobs are running
        for job in jobs:
            db.session.refresh(job)
            assert job.status in [JobStatus.RUNNING, JobStatus.PENDING]
        
        # Cleanup threads
        for thread in threads:
            thread.join(timeout=1.0)
    
    def test_error_handling_and_recovery(self, batch_manager):
        """Test error handling and recovery mechanisms"""
        # Create job that will fail
        job = batch_manager.create_job(
            name="Error Test Job",
            analysis_types=["security_analysis"],
            models_to_analyze=["nonexistent_model"],
            app_range="1"
        )
        tasks = batch_manager.generate_tasks(job.id)
        
        # Mock service to raise exception
        with patch('batch_service.SecurityAnalysisService') as mock_service:
            mock_service.return_value.run_security_analysis.side_effect = Exception("Test error")
            
            runner = BatchTaskRunner()
            result = runner.execute_task(tasks[0].id)
            
            # Task should be marked as failed
            db.session.refresh(tasks[0])
            assert tasks[0].status == TaskStatus.FAILED
            assert "Test error" in tasks[0].error_message
    
    def test_memory_and_resource_management(self, batch_manager):
        """Test memory usage and resource cleanup"""
        import psutil
        import gc
        
        # Get initial memory usage
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        # Create many jobs and tasks
        jobs = []
        for i in range(10):
            job = batch_manager.create_job(
                name=f"Memory Test Job {i}",
                analysis_types=["security_analysis"],
                models_to_analyze=["test_model"],
                app_range="1-10"
            )
            batch_manager.generate_tasks(job.id)
            jobs.append(job)
        
        # Force garbage collection
        gc.collect()
        
        # Check memory usage hasn't grown excessively
        current_memory = process.memory_info().rss
        memory_growth = current_memory - initial_memory
        
        # Allow for reasonable memory growth (less than 100MB)
        assert memory_growth < 100 * 1024 * 1024, f"Memory growth too large: {memory_growth} bytes"


class TestBatchRoutes:
    """Test batch routes and API endpoints"""
    
    @pytest.fixture
    def app(self):
        """Create test Flask application"""
        app = create_app()
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['WTF_CSRF_ENABLED'] = False
        
        with app.app_context():
            db.create_all()
            yield app
            db.drop_all()
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return app.test_client()
    
    def test_dashboard_page_loads(self, client):
        """Test batch dashboard page loads correctly"""
        response = client.get('/batch/dashboard')
        assert response.status_code == 200
        assert b'Batch Analysis Dashboard' in response.data
        assert b'stats-grid' in response.data
    
    def test_create_job_api(self, client):
        """Test job creation via API"""
        job_data = {
            "name": "API Test Job",
            "description": "Testing job creation via API",
            "analysis_types": ["security_analysis"],
            "models": ["test_model"],
            "app_range": "1-3",
            "priority": "normal"
        }
        
        response = client.post(
            '/api/batch/jobs',
            data=json.dumps(job_data),
            content_type='application/json'
        )
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert 'job_id' in data
        assert data['status'] == 'success'
    
    def test_invalid_job_creation(self, client):
        """Test validation of invalid job data"""
        invalid_data = {
            "name": "",  # Empty name
            "analysis_types": [],  # No analysis types
            "models": [],  # No models
            "app_range": "invalid"  # Invalid range
        }
        
        response = client.post(
            '/api/batch/jobs',
            data=json.dumps(invalid_data),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_job_list_api(self, client):
        """Test job listing API with pagination"""
        # Create test jobs
        for i in range(15):
            job_data = {
                "name": f"Test Job {i}",
                "analysis_types": ["security_analysis"],
                "models": ["test_model"],
                "app_range": "1"
            }
            client.post(
                '/api/batch/jobs',
                data=json.dumps(job_data),
                content_type='application/json'
            )
        
        # Test pagination
        response = client.get('/api/batch/jobs?page=1&per_page=10')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert len(data['jobs']) == 10
        assert data['pagination']['total'] == 15
        assert data['pagination']['pages'] == 2
    
    def test_job_filtering(self, client):
        """Test job filtering by status and other criteria"""
        # Create jobs with different statuses
        with client.application.app_context():
            from models import BatchJob, JobStatus
            
            job1 = BatchJob(
                name="Running Job",
                status=JobStatus.RUNNING,
                analysis_types=[AnalysisType.SECURITY_ANALYSIS],
                models_to_analyze=["test_model"],
                app_range="1"
            )
            job2 = BatchJob(
                name="Completed Job",
                status=JobStatus.COMPLETED,
                analysis_types=[AnalysisType.SECURITY_ANALYSIS],
                models_to_analyze=["test_model"],
                app_range="1"
            )
            
            db.session.add_all([job1, job2])
            db.session.commit()
        
        # Test status filtering
        response = client.get('/api/batch/jobs?status=running')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert len(data['jobs']) == 1
        assert data['jobs'][0]['status'] == 'running'
    
    def test_job_control_operations(self, client):
        """Test job control operations (start, stop, cancel)"""
        # Create a job
        job_data = {
            "name": "Control Test Job",
            "analysis_types": ["security_analysis"],
            "models": ["test_model"],
            "app_range": "1"
        }
        
        response = client.post(
            '/api/batch/jobs',
            data=json.dumps(job_data),
            content_type='application/json'
        )
        data = json.loads(response.data)
        job_id = data['job_id']
        
        # Test job start
        response = client.post(f'/api/batch/jobs/{job_id}/start')
        assert response.status_code == 200
        
        # Test job cancel
        response = client.post(f'/api/batch/jobs/{job_id}/cancel')
        assert response.status_code == 200
    
    def test_statistics_api(self, client):
        """Test statistics API endpoint"""
        response = client.get('/api/batch/statistics')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'jobs' in data
        assert 'worker_pool' in data
        assert 'system_resources' in data
        
        # Verify structure
        assert 'total' in data['jobs']
        assert 'by_status' in data['jobs']
        assert 'active_workers' in data['worker_pool']
    
    def test_bulk_operations(self, client):
        """Test bulk operations on multiple jobs"""
        # Create multiple jobs
        job_ids = []
        for i in range(5):
            job_data = {
                "name": f"Bulk Test Job {i}",
                "analysis_types": ["security_analysis"],
                "models": ["test_model"],
                "app_range": "1"
            }
            response = client.post(
                '/api/batch/jobs',
                data=json.dumps(job_data),
                content_type='application/json'
            )
            data = json.loads(response.data)
            job_ids.append(data['job_id'])
        
        # Test bulk cancel
        bulk_data = {"job_ids": job_ids}
        response = client.post(
            '/api/batch/jobs/bulk-cancel',
            data=json.dumps(bulk_data),
            content_type='application/json'
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['cancelled_count'] == 5
    
    def test_export_functionality(self, client):
        """Test job export in various formats"""
        # Create test job
        job_data = {
            "name": "Export Test Job",
            "analysis_types": ["security_analysis"],
            "models": ["test_model"],
            "app_range": "1"
        }
        response = client.post(
            '/api/batch/jobs',
            data=json.dumps(job_data),
            content_type='application/json'
        )
        
        # Test CSV export
        response = client.get('/api/batch/jobs/export?format=csv')
        assert response.status_code == 200
        assert response.headers['Content-Type'] == 'text/csv; charset=utf-8'
        
        # Test JSON export
        response = client.get('/api/batch/jobs/export?format=json')
        assert response.status_code == 200
        assert response.headers['Content-Type'] == 'application/json'
    
    def test_real_time_progress_endpoint(self, client):
        """Test real-time progress WebSocket-like endpoint"""
        # Create job with tasks
        job_data = {
            "name": "Progress Test Job",
            "analysis_types": ["security_analysis"],
            "models": ["test_model"],
            "app_range": "1-5"
        }
        response = client.post(
            '/api/batch/jobs',
            data=json.dumps(job_data),
            content_type='application/json'
        )
        data = json.loads(response.data)
        job_id = data['job_id']
        
        # Test progress endpoint
        response = client.get(f'/api/batch/jobs/{job_id}/progress')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'progress_percentage' in data
        assert 'total_tasks' in data
        assert 'completed_tasks' in data
        assert 'eta' in data


class TestIntegration:
    """Integration tests for complete batch system"""
    
    @pytest.fixture
    def app(self):
        """Create test Flask application with full configuration"""
        app = create_app()
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        with app.app_context():
            db.create_all()
            
            # Create test data
            self._create_test_data()
            
            yield app
            db.drop_all()
    
    def _create_test_data(self):
        """Create realistic test data"""
        # Create some generated applications
        models = ['anthropic_claude-3.7-sonnet', 'openai_gpt-4', 'test_model']
        
        for model in models:
            for app_num in range(1, 6):
                app = GeneratedApplication(
                    model_name=model,
                    app_number=app_num,
                    app_type='web_app',
                    status='completed'
                )
                db.session.add(app)
        
        db.session.commit()
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return app.test_client()
    
    def test_complete_job_lifecycle(self, client):
        """Test complete job lifecycle from creation to completion"""
        # 1. Create job via API
        job_data = {
            "name": "Integration Test Job",
            "description": "Full lifecycle test",
            "analysis_types": ["security_analysis", "zap_scan"],
            "models": ["test_model"],
            "app_range": "1-3",
            "priority": "high",
            "auto_start": True
        }
        
        response = client.post(
            '/api/batch/jobs',
            data=json.dumps(job_data),
            content_type='application/json'
        )
        assert response.status_code == 201
        
        job_id = json.loads(response.data)['job_id']
        
        # 2. Verify job was created with correct tasks
        response = client.get(f'/api/batch/jobs/{job_id}')
        assert response.status_code == 200
        
        job_data = json.loads(response.data)
        assert job_data['name'] == "Integration Test Job"
        assert job_data['total_tasks'] == 6  # 2 analysis types × 3 apps
        
        # 3. Check initial progress
        response = client.get(f'/api/batch/jobs/{job_id}/progress')
        assert response.status_code == 200
        
        progress = json.loads(response.data)
        assert progress['progress_percentage'] == 0.0
        
        # 4. Simulate task completion
        with client.application.app_context():
            from models import BatchTask, TaskStatus
            
            tasks = BatchTask.query.filter_by(job_id=job_id).all()
            
            # Complete half the tasks
            for i, task in enumerate(tasks[:3]):
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.utcnow()
            
            db.session.commit()
        
        # 5. Check updated progress
        response = client.get(f'/api/batch/jobs/{job_id}/progress')
        progress = json.loads(response.data)
        assert progress['progress_percentage'] == 50.0
        assert progress['completed_tasks'] == 3
        
        # 6. Complete remaining tasks
        with client.application.app_context():
            remaining_tasks = BatchTask.query.filter_by(
                job_id=job_id,
                status=TaskStatus.PENDING
            ).all()
            
            for task in remaining_tasks:
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.utcnow()
            
            db.session.commit()
        
        # 7. Verify job completion
        response = client.get(f'/api/batch/jobs/{job_id}')
        job_data = json.loads(response.data)
        assert job_data['status'] == 'completed'
        
        response = client.get(f'/api/batch/jobs/{job_id}/progress')
        progress = json.loads(response.data)
        assert progress['progress_percentage'] == 100.0
    
    def test_error_handling_integration(self, client):
        """Test error handling throughout the system"""
        # Test invalid job creation
        invalid_job = {
            "name": "",
            "analysis_types": [],
            "models": [],
            "app_range": "invalid"
        }
        
        response = client.post(
            '/api/batch/jobs',
            data=json.dumps(invalid_job),
            content_type='application/json'
        )
        assert response.status_code == 400
        
        # Test accessing non-existent job
        response = client.get('/api/batch/jobs/99999')
        assert response.status_code == 404
        
        # Test invalid bulk operations
        response = client.post(
            '/api/batch/jobs/bulk-cancel',
            data=json.dumps({"job_ids": []}),
            content_type='application/json'
        )
        assert response.status_code == 400
    
    def test_concurrent_access(self, client):
        """Test concurrent access to the system"""
        import threading
        import queue
        
        results = queue.Queue()
        
        def create_job(index):
            try:
                job_data = {
                    "name": f"Concurrent Job {index}",
                    "analysis_types": ["security_analysis"],
                    "models": ["test_model"],
                    "app_range": "1-2"
                }
                
                response = client.post(
                    '/api/batch/jobs',
                    data=json.dumps(job_data),
                    content_type='application/json'
                )
                
                results.put(response.status_code)
            except Exception as e:
                results.put(str(e))
        
        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=create_job, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Check results
        success_count = 0
        while not results.empty():
            result = results.get()
            if result == 201:
                success_count += 1
        
        assert success_count >= 8  # Allow for some potential race conditions
    
    def test_performance_under_load(self, client):
        """Test system performance under load"""
        import time
        
        start_time = time.time()
        
        # Create many jobs quickly
        for i in range(50):
            job_data = {
                "name": f"Load Test Job {i}",
                "analysis_types": ["security_analysis"],
                "models": ["test_model"],
                "app_range": "1"
            }
            
            response = client.post(
                '/api/batch/jobs',
                data=json.dumps(job_data),
                content_type='application/json'
            )
            
            # Most requests should succeed
            assert response.status_code in [201, 429]  # 429 = rate limited
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should handle 50 requests in reasonable time (less than 30 seconds)
        assert duration < 30.0, f"Performance test took too long: {duration} seconds"
        
        # Verify jobs were created
        response = client.get('/api/batch/jobs?per_page=100')
        data = json.loads(response.data)
        assert len(data['jobs']) >= 40  # Allow for some rate limiting


if __name__ == '__main__':
    # Run specific test categories
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == 'models':
            pytest.main(['-v', 'TestDatabaseModels'])
        elif sys.argv[1] == 'services':
            pytest.main(['-v', 'TestBatchService'])
        elif sys.argv[1] == 'routes':
            pytest.main(['-v', 'TestBatchRoutes'])
        elif sys.argv[1] == 'integration':
            pytest.main(['-v', 'TestIntegration'])
        else:
            print("Usage: python test_batch_system.py [models|services|routes|integration]")
    else:
        # Run all tests
        pytest.main(['-v', __file__])
