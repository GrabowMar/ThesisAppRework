from app.services.analysis_engines import get_engine, ENGINE_REGISTRY


class DummyIntegration:
    def run_security_analysis(self, model_slug, app_number, tools=None, options=None):
        return {'status': 'completed', 'kind': 'security', 'tools': tools or []}

    def run_performance_test(self, model_slug, app_number, test_config=None):
        return {'status': 'completed', 'kind': 'performance', 'config': test_config or {}}

    def run_static_analysis(self, model_slug, app_number, tools=None, options=None):
        return {'status': 'completed', 'kind': 'static'}

    def run_dynamic_analysis(self, model_slug, app_number, options=None):
        return {'status': 'completed', 'kind': 'dynamic'}


def patch_integration(monkeypatch):
    # Patch get_analyzer_integration to return dummy
    import app.services.analysis_engines as engines_mod
    monkeypatch.setattr(engines_mod, 'get_analyzer_integration', lambda: DummyIntegration())
    # Force re-init of engines (they resolve integration on instantiation)


def test_registry_contains_expected_engines():
    assert {'security', 'performance', 'static', 'dynamic'}.issubset(ENGINE_REGISTRY.keys())


def test_security_engine_run(monkeypatch):
    patch_integration(monkeypatch)
    engine = get_engine('security')
    result = engine.run('model_x', 1, tools=['bandit']).to_dict()
    assert result['engine'] == 'security'
    assert result['payload']['kind'] == 'security'
    assert result['payload']['tools'] == ['bandit']


def test_performance_engine_run(monkeypatch):
    patch_integration(monkeypatch)
    engine = get_engine('performance')
    result = engine.run('m', 2, test_config={'users': 5}).to_dict()
    assert result['engine'] == 'performance'
    assert result['payload']['config']['users'] == 5


def test_dynamic_engine_run(monkeypatch):
    patch_integration(monkeypatch)
    engine = get_engine('dynamic')
    result = engine.run('m', 3).to_dict()
    assert result['payload']['kind'] == 'dynamic'


def test_static_engine_run(monkeypatch):
    patch_integration(monkeypatch)
    engine = get_engine('static')
    result = engine.run('m', 4).to_dict()
    assert result['payload']['kind'] == 'static'