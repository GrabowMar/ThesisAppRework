import pytest

from app.utils.port_resolution import resolve_ports
from app.models import db, PortConfiguration, ModelCapability


def _add_model(slug: str, name: str | None = None):
    m = ModelCapability()
    m.canonical_slug = slug
    m.model_name = name or slug
    m.provider = slug.split('_')[0] if '_' in slug else 'prov'
    db.session.add(m)
    db.session.commit()
    return m

def _add_port(model: str, app_num: int, backend: int, frontend: int):
    pc = PortConfiguration()
    pc.model = model
    pc.app_num = app_num
    pc.backend_port = backend
    pc.frontend_port = frontend
    db.session.add(pc)
    db.session.commit()
    return pc

@pytest.mark.parametrize("slug_variant,stored", [
    ("alpha_model_x", "alpha_model_x"),           # exact
    ("alpha-model-x", "alpha_model_x"),           # separator normalization
])
@pytest.mark.usefixtures("app")
def test_resolve_ports_exact_and_normalized(slug_variant, stored):
    _add_model(stored)
    _add_port(stored, 1, 5001, 3001)
    result = resolve_ports(slug_variant, 1, include_attempts=True)
    assert result is not None
    assert result['backend'] == 5001
    assert result['frontend'] == 3001

@pytest.mark.usefixtures("app")
def test_resolve_ports_model_attr_fallback():
    # Store ports under model_name but lookup via canonical slug
    m = _add_model("provider_canonical")
    stored_name = m.model_name
    _add_port(stored_name, 2, 6001, 4001)
    result = resolve_ports("provider_canonical", 2, include_attempts=True)
    assert result is not None
    assert result['backend'] == 6001
    assert 'model_attr' in result['source']

@pytest.mark.usefixtures("app")
def test_resolve_ports_fuzzy_tokens():
    _add_model("gamma_ultra")
    _add_port("gamma-ultra", 3, 7001, 9001)
    result = resolve_ports("gamma_ultra", 3, include_attempts=True)
    assert result is not None
    assert result['backend'] == 7001
    assert 'fuzzy' in result['source'] or 'normalized' in result['source'] or 'alnum' in result['source']

@pytest.mark.usefixtures("app")
def test_resolve_ports_alnum_norm():
    _add_model("deltaX.model")
    _add_port("deltaX_model", 4, 8100, 8200)
    result = resolve_ports("deltaX.model", 4, include_attempts=True)
    assert result is not None
    assert result['backend'] == 8100
    # Accept any of the later-stage sources
    assert any(k in result['source'] for k in ['alnum', 'normalized'])

@pytest.mark.usefixtures("app")
def test_resolve_ports_not_found():
    _add_model("omega_missing")
    result = resolve_ports("omega_missing", 9, include_attempts=True)
    assert result is None
