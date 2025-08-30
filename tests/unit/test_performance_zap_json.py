from app.models import (
    db,
    GeneratedApplication,
    SecurityAnalysis,
    PerformanceTest,
    ZAPAnalysis,
    AnalysisStatus,
)


def _seed_app():
    ga = GeneratedApplication()
    ga.model_slug = 'test_model'
    ga.app_number = 1
    ga.app_type = 'web'
    ga.provider = 'test-provider'
    db.session.add(ga)
    db.session.commit()
    return ga


def test_analysis_dashboard_loads_successfully(client, app):
    """Analysis dashboard should load successfully with basic stats."""
    # Seed app inside context
    with app.app_context():
        _seed_app()

    # Test the new simplified dashboard
    resp = client.get('/analysis/')
    assert resp.status_code == 200
    
    # Should contain dashboard elements
    assert b'Analysis Dashboard' in resp.data
    assert b'Quick Actions' in resp.data


def test_performance_and_zap_results_json_roundtrip(app):
    """Persist JSON results for performance & ZAP analyses and ensure model accessors deserialize."""
    with app.app_context():
        ga = _seed_app()
        perf = PerformanceTest()
        perf.application_id = ga.id
        perf.status = AnalysisStatus.RUNNING
        zap = ZAPAnalysis()
        zap.application_id = ga.id
        zap.target_url = 'http://localhost:6101'
        zap.scan_type = 'active'
        zap.status = AnalysisStatus.RUNNING
        db.session.add_all([perf, zap])
        db.session.commit()

        perf_payload = {
            'model_slug': ga.model_slug,
            'app_number': ga.app_number,
            'results': {
                'url_1': {
                    'locust': {
                        'summary': {
                            'requests_per_second': 123.4,
                            'p95_response_time_ms': 450.0
                        }
                    }
                }
            },
            'summary': {'average_response_time': 210.5}
        }
        zap_payload = {
            'target': 'http://localhost:6101',
            'alert_counts': {'High': 1, 'Medium': 2, 'Low': 0, 'Informational': 3},
            'total_alerts': 6,
            'active_scan': {'status': 'completed'}
        }
        perf.set_results(perf_payload)
        zap.set_zap_report(zap_payload)  # type: ignore[attr-defined]
        perf.status = AnalysisStatus.COMPLETED
        zap.status = AnalysisStatus.COMPLETED
        db.session.commit()
        perf_id = perf.id
        zap_id = zap.id

    # Open fresh context and reload by ID to avoid detached attribute refresh
    with app.app_context():
        perf_loaded = db.session.get(PerformanceTest, perf_id)
        zap_loaded = db.session.get(ZAPAnalysis, zap_id)
        assert perf_loaded is not None and zap_loaded is not None
        perf_results = perf_loaded.get_results()
        zap_results = zap_loaded.get_zap_report()  # type: ignore[attr-defined]
        assert perf_results.get('results', {}).get('url_1', {}).get('locust') is not None
        assert zap_results.get('alert_counts', {}).get('High') == 1
        assert perf_results['summary']['average_response_time'] == 210.5
        assert zap_results['total_alerts'] == 6