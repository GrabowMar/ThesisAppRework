"""Test statistics routes functionality."""


class TestStatisticsRoutes:
    """Test statistics route endpoints."""
    
    def test_statistics_dashboard_access(self, client):
        """Test access to statistics dashboard."""
        response = client.get('/statistics/')
        assert response.status_code == 200
        
    def test_security_statistics_endpoint(self, client):
        """Test security statistics API endpoint."""
        response = client.get('/statistics/api/security-statistics')
        assert response.status_code == 200
        
    def test_performance_statistics_endpoint(self, client):
        """Test performance statistics API endpoint."""
        response = client.get('/statistics/api/performance-statistics')
        assert response.status_code == 200
        
    def test_batch_statistics_endpoint(self, client):
        """Test batch statistics API endpoint."""
        response = client.get('/statistics/api/batch-statistics')
        assert response.status_code == 200
        
    def test_analysis_trends_endpoint(self, client):
        """Test analysis trends API endpoint."""
        response = client.get('/statistics/api/analysis-trends')
        assert response.status_code == 200
        
    def test_model_comparison_endpoint(self, client):
        """Test model comparison API endpoint."""
        response = client.get('/statistics/api/model-comparison')
        assert response.status_code == 200
        
    def test_top_vulnerabilities_endpoint(self, client):
        """Test top vulnerabilities API endpoint."""
        response = client.get('/statistics/api/top-vulnerabilities')
        assert response.status_code == 200
        
    def test_activity_timeline_endpoint(self, client):
        """Test activity timeline API endpoint."""
        response = client.get('/statistics/api/activity-timeline')
        assert response.status_code == 200
        
    def test_advanced_statistics_access(self, client):
        """Test access to advanced statistics page."""
        response = client.get('/statistics/advanced')
        assert response.status_code == 200
        
    def test_statistics_with_date_filters(self, client):
        """Test statistics endpoints with date filters."""
        response = client.get('/statistics/api/activity-timeline?start_date=2024-01-01&end_date=2024-12-31')
        assert response.status_code == 200
