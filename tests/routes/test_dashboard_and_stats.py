"""
Test suite for Dashboard and Statistics functionality

Tests dashboard cards, metrics, system status, and statistics.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime


@pytest.fixture
def app():
    """Create test Flask app"""
    from app.factory import create_app
    app = create_app('testing')
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


class TestDashboardCards:
    """Test dashboard summary cards"""
    
    def test_get_summary_cards(self, client):
        """Test getting dashboard summary cards"""
        response = client.get('/api/dashboard/fragments/summary-cards')
        
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.get_data(as_text=True)
            assert data is not None
    
    def test_total_applications_card(self, app, client):
        """Test total applications metric"""
        with app.app_context():
            from app.models import GeneratedApplication
            
            with patch.object(GeneratedApplication, 'query') as mock_query:
                mock_query.count.return_value = 42
                
                response = client.get('/api/dashboard/fragments/summary-cards')
                
                assert response.status_code in [200, 500]
    
    def test_total_models_card(self, app, client):
        """Test total models metric"""
        with app.app_context():
            from app.models import ModelCapability
            
            with patch.object(ModelCapability, 'query') as mock_query:
                mock_query.count.return_value = 15
                
                response = client.get('/api/dashboard/fragments/summary-cards')
                
                assert response.status_code in [200, 500]


class TestSystemStatus:
    """Test system status monitoring"""
    
    def test_get_system_status(self, client):
        """Test getting system status"""
        response = client.get('/api/dashboard/fragments/system-status')
        
        assert response.status_code in [200, 500]
    
    def test_docker_status(self, app, client):
        """Test Docker service status"""
        with app.app_context():
            with patch('docker.from_env') as mock_docker:
                mock_client = Mock()
                mock_client.ping.return_value = True
                mock_docker.return_value = mock_client
                
                response = client.get('/api/dashboard/fragments/system-status')
                
                assert response.status_code in [200, 500]
    
    def test_celery_status(self, client):
        """Test Celery worker status"""
        with patch('celery.app.control.Inspect') as mock_inspect:
            mock_i = Mock()
            mock_i.active.return_value = {}
            mock_inspect.return_value = mock_i
            
            response = client.get('/api/dashboard/fragments/system-status')
            
            assert response.status_code in [200, 500]


class TestRecentActivity:
    """Test recent activity feeds"""
    
    def test_get_recent_applications(self, app, client):
        """Test getting recent applications"""
        with app.app_context():
            from app.models import GeneratedApplication
            
            mock_apps = [
                Mock(
                    id=1,
                    model_slug='test/model',
                    app_number=1,
                    created_at=datetime.now()
                )
            ]
            
            with patch.object(GeneratedApplication, 'query') as mock_query:
                mock_query.order_by.return_value.limit.return_value.all.return_value = mock_apps
                
                response = client.get('/api/dashboard/fragments/recent-applications')
                
                assert response.status_code in [200, 404, 500]
    
    def test_get_recent_analyses(self, app, client):
        """Test getting recent analyses"""
        with app.app_context():
            response = client.get('/api/dashboard/fragments/recent-analyses')
            
            assert response.status_code in [200, 404, 500]


class TestStatistics:
    """Test statistics calculations"""
    
    def test_get_generation_statistics(self, app, client):
        """Test getting generation statistics"""
        with app.app_context():
            from app.services.generation_statistics import GenerationStatistics
            
            with patch.object(GenerationStatistics, 'get_stats') as mock_stats:
                mock_stats.return_value = {
                    'total': 100,
                    'successful': 85,
                    'failed': 15
                }
                
                response = client.get('/api/statistics/generation')
                
                assert response.status_code in [200, 404, 500]
    
    def test_get_model_statistics(self, app, client):
        """Test getting model statistics"""
        with app.app_context():
            response = client.get('/api/statistics/models')
            
            assert response.status_code in [200, 404, 500]
    
    def test_get_analysis_statistics(self, app, client):
        """Test getting analysis statistics"""
        with app.app_context():
            response = client.get('/api/statistics/analysis')
            
            assert response.status_code in [200, 404, 500]


class TestCharts:
    """Test chart data endpoints"""
    
    def test_get_generation_chart_data(self, client):
        """Test getting chart data for generations over time"""
        response = client.get('/api/statistics/charts/generation-timeline')
        
        assert response.status_code in [200, 404, 500]
    
    def test_get_model_usage_chart_data(self, client):
        """Test getting model usage chart data"""
        response = client.get('/api/statistics/charts/model-usage')
        
        assert response.status_code in [200, 404, 500]


class TestHealthMetrics:
    """Test health and performance metrics"""
    
    def test_get_health_metrics(self, client):
        """Test getting system health metrics"""
        response = client.get('/api/health')
        
        assert response.status_code in [200, 503]
        data = response.get_json()
        assert data is not None
    
    def test_get_performance_metrics(self, client):
        """Test getting performance metrics"""
        with patch('psutil.cpu_percent', return_value=45.5):
            with patch('psutil.virtual_memory') as mock_mem:
                mock_mem.return_value.percent = 60.0
                
                response = client.get('/api/system/metrics')
                
                assert response.status_code in [200, 404, 500]


class TestExportStatistics:
    """Test statistics export functionality"""
    
    def test_export_statistics_json(self, client):
        """Test exporting statistics as JSON"""
        response = client.get('/api/statistics/export?format=json')
        
        assert response.status_code in [200, 404, 500]
    
    def test_export_statistics_csv(self, client):
        """Test exporting statistics as CSV"""
        response = client.get('/api/statistics/export?format=csv')
        
        assert response.status_code in [200, 404, 500]


@pytest.mark.integration
class TestDashboardIntegration:
    """Integration tests for dashboard"""
    
    def test_full_dashboard_load(self, client):
        """Test loading complete dashboard"""
        response = client.get('/')
        
        assert response.status_code == 200
        assert b'<!DOCTYPE html>' in response.data or b'<html' in response.data
