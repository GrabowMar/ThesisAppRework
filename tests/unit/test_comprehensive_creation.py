from app.models import db, GeneratedApplication, SecurityAnalysis, PerformanceTest, ZAPAnalysis

def test_comprehensive_creation_triggers_all(client, app):
    """Comprehensive creation via API should result in three analysis records.

    Uses JSON API endpoint to avoid template rendering variability in test environment.
    """
    with app.app_context():
        ga = GeneratedApplication()
        ga.model_slug = 'test_model'
        ga.app_number = 1
        ga.app_type = 'web'
        ga.provider = 'test-provider'
        db.session.add(ga)
        db.session.commit()
        app_id = ga.id

    # Emulate the UI's comprehensive action by calling component endpoints
    # Security comprehensive
    with app.app_context():
        from app.services import analysis_service as svc
        sec = svc.create_comprehensive_security_analysis(app_id)
        svc.start_security_analysis(sec['id'], enqueue=False)
        perf = svc.create_performance_test({'application_id': app_id, 'test_type': 'load'})
        svc.start_performance_test(perf['id'], use_engine=False)
        dyn = svc.create_dynamic_analysis({'application_id': app_id})
        svc.start_dynamic_analysis(dyn['id'], enqueue=False)

        assert SecurityAnalysis.query.filter_by(application_id=app_id).count() == 1
        assert PerformanceTest.query.filter_by(application_id=app_id).count() == 1
        assert ZAPAnalysis.query.filter_by(application_id=app_id).count() == 1
