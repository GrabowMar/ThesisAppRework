"""Test analysis routes functionality."""


class TestAnalysisRoutes:
    """Test analysis route endpoints."""
    
    def test_security_analysis_start(self, client, clean_db):
        """Test starting security analysis."""
        from src.app.models import GeneratedApplication
        
        # Create test application
        app = GeneratedApplication()
        app.model_slug = 'test_model'
        app.app_number = 1
        app.provider = 'test'
        
        clean_db.session.add(app)
        clean_db.session.commit()
        
        response = client.post(f'/analysis/security/{app.id}/start')
        assert response.status_code in [200, 302, 404]  # Success, redirect, or not found
        
    def test_performance_analysis_start(self, client, clean_db):
        """Test starting performance analysis."""
        from src.app.models import GeneratedApplication
        
        # Create test application
        app = GeneratedApplication()
        app.model_slug = 'test_model'
        app.app_number = 1
        app.provider = 'test'
        
        clean_db.session.add(app)
        clean_db.session.commit()
        
        response = client.post(f'/analysis/performance/{app.id}/start')
        assert response.status_code in [200, 302, 404]  # Success, redirect, or not found
        
    def test_zap_analysis_start(self, client, clean_db):
        """Test starting ZAP analysis."""
        from src.app.models import GeneratedApplication
        
        # Create test application
        app = GeneratedApplication()
        app.model_slug = 'test_model'
        app.app_number = 1
        app.provider = 'test'
        
        clean_db.session.add(app)
        clean_db.session.commit()
        
        response = client.post(f'/analysis/zap/{app.id}/start')
        assert response.status_code in [200, 302, 404]  # Success, redirect, or not found
        
    def test_openrouter_analysis_start(self, client, clean_db):
        """Test starting OpenRouter analysis."""
        from src.app.models import GeneratedApplication
        
        # Create test application
        app = GeneratedApplication()
        app.model_slug = 'test_model'
        app.app_number = 1
        app.provider = 'test'
        
        clean_db.session.add(app)
        clean_db.session.commit()
        
        response = client.post(f'/analysis/openrouter/{app.id}/start')
        assert response.status_code in [200, 302, 404]  # Success, redirect, or not found
        
    def test_analysis_status_endpoints(self, client, clean_db):
        """Test analysis status endpoints."""
        from src.app.models import SecurityAnalysis, PerformanceTest
        from src.app.constants import AnalysisStatus
        
        # Create sample security analysis
        security_analysis = SecurityAnalysis()
        security_analysis.application_id = 1
        security_analysis.status = AnalysisStatus.COMPLETED
        security_analysis.total_issues = 5
        
        clean_db.session.add(security_analysis)
        clean_db.session.commit()
        
        response = client.get(f'/analysis/security/{security_analysis.id}/status')
        assert response.status_code == 200
        
        # Create sample performance test
        perf_test = PerformanceTest()
        perf_test.application_id = 1
        perf_test.status = AnalysisStatus.RUNNING
        perf_test.test_type = 'load'
        
        clean_db.session.add(perf_test)
        clean_db.session.commit()
        
        response = client.get(f'/analysis/performance/{perf_test.id}/status')
        assert response.status_code == 200
        
    def test_analysis_results_endpoints(self, client, clean_db):
        """Test analysis results endpoints."""
        from src.app.models import SecurityAnalysis, PerformanceTest
        from src.app.constants import AnalysisStatus
        
        # Create sample completed security analysis
        security_analysis = SecurityAnalysis()
        security_analysis.application_id = 1
        security_analysis.status = AnalysisStatus.COMPLETED
        security_analysis.total_issues = 3
        security_analysis.results_json = '{"vulnerabilities": []}'
        
        clean_db.session.add(security_analysis)
        clean_db.session.commit()
        
        response = client.get(f'/analysis/security/{security_analysis.id}/results')
        assert response.status_code == 200
        
        # Create sample completed performance test
        perf_test = PerformanceTest()
        perf_test.application_id = 1
        perf_test.status = AnalysisStatus.COMPLETED
        perf_test.requests_per_second = 100.5
        perf_test.average_response_time = 200.0
        
        clean_db.session.add(perf_test)
        clean_db.session.commit()
        
        response = client.get(f'/analysis/performance/{perf_test.id}/results')
        assert response.status_code == 200
