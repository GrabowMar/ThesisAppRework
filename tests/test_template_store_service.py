from pathlib import Path
import pytest

from app.services.template_store_service import TemplateStoreService, Profile


@pytest.fixture()
def isolated_store(tmp_path: Path):
    # Build isolated directories
    code_dir = tmp_path / 'code_templates'
    app_dir = tmp_path / 'app_templates'
    profiles_dir = tmp_path / 'profiles'
    history_dir = tmp_path / '.history'
    for d in (code_dir, app_dir, profiles_dir, history_dir):
        d.mkdir(parents=True, exist_ok=True)

    store = TemplateStoreService(auto_migrate=False)
    # Redirect directories to isolation layer
    store.code_dir = code_dir
    store.app_dir = app_dir
    store.profiles_dir = profiles_dir
    store.history_dir = history_dir
    return store


def test_save_and_read_creates_file_and_detects_placeholders(isolated_store: TemplateStoreService):
    content_v1 = """# Demo\nprint('Hello {{name}}')\n# again {{ name }}"""
    meta = isolated_store.save('code', 'demo/hello.py.template', content_v1)
    assert meta['placeholders'] == ['name']

    read_back = isolated_store.read('code', 'demo/hello.py.template')
    assert 'Hello' in read_back['content']
    assert read_back['placeholders'] == ['name']


def test_versioning_creates_backup_file(isolated_store: TemplateStoreService):
    path = 'service/api.py.template'
    isolated_store.save('code', path, 'print("v1 {{port}}")')
    # second save triggers backup
    isolated_store.save('code', path, 'print("v2 {{port}}")')
    hist_dir = isolated_store._history_dir_for('code', path)
    backups = list(hist_dir.glob('*.bak'))
    assert len(backups) == 1, f"Expected exactly one backup, found {len(backups)}"


def test_list_returns_both_categories(isolated_store: TemplateStoreService):
    isolated_store.save('code', 'a.txt', 'code')
    isolated_store.save('app', 'b.txt', 'app')
    metas = isolated_store.list()
    cats = {m.category for m in metas}
    assert {'code', 'app'} <= cats


def test_delete_returns_true_then_false(isolated_store: TemplateStoreService):
    isolated_store.save('code', 'todelete.txt', 'x')
    assert isolated_store.delete('code', 'todelete.txt') is True
    assert isolated_store.delete('code', 'todelete.txt') is False


def test_profile_crud(isolated_store: TemplateStoreService):
    prof = Profile(name='basic', description='Basic profile', templates=['a.txt', 'b.txt'], config={'k': 'v'})
    isolated_store.save_profile(prof)
    listed = isolated_store.list_profiles()
    assert any(p.name == 'basic' for p in listed)
    assert isolated_store.delete_profile('basic') is True
    assert isolated_store.delete_profile('basic') is False
