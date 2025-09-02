import os
import asyncio
from pathlib import Path
from app.services.sample_generation_service import get_sample_generation_service, Template


def test_scaffold_parity_minimax(tmp_path, monkeypatch):
    # Point generated output to a temp directory to isolate test
    monkeypatch.chdir(tmp_path)
    os.environ['OPENROUTER_API_KEY'] = ''
    svc = get_sample_generation_service()
    # Redirect organizer output dir and reset cache for clean run
    svc.organizer.output_dir = Path('generated')
    svc.organizer._scaffold_cache.clear()

    # Ensure code templates directory exists (copy from repo if present)
    repo_templates = Path(__file__).parent.parent / 'misc' / 'code_templates'
    if repo_templates.exists():
        # Mirror minimal structure
        (Path('misc') / 'code_templates').mkdir(parents=True, exist_ok=True)
        for src in repo_templates.rglob('*'):
            if src.is_file():
                dest = Path('misc') / 'code_templates' / src.relative_to(repo_templates)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(src.read_text(encoding='utf-8', errors='ignore'), encoding='utf-8')

    # Add template and generate
    t = Template(app_num=1, name='scaffold_check', content='Return status endpoint', requirements=['Flask'])
    svc.template_registry.templates.clear()
    svc.template_registry.templates.append(t)

    asyncio.run(svc.generate_async('1', 'minimax/minimax-12b-chat'))

    # Verify scaffold directories exist
    model_folder = 'minimax_minimax-12b-chat'
    app_dir = Path('generated') / model_folder / 'app1'
    assert app_dir.exists(), f"App directory missing: {app_dir}"
    # Check presence of scaffolded backend files (app.py or requirements.txt from template set)
    backend_dir = app_dir / 'backend'
    assert backend_dir.exists(), 'Backend directory not scaffolded'
    # Templates have requirements.txt template; ensure either original or generated exists
    req_files = list(backend_dir.glob('requirements.txt'))
    assert req_files, 'requirements.txt missing in backend scaffold'
    # Validate placeholder substitution in backend app.py
    app_py = backend_dir / 'app.py'
    # The scaffolded file may remain untouched; generated code goes to generated_app.py if collision
    content_files = []
    if app_py.exists():
        content_files.append(app_py.read_text(encoding='utf-8'))
    gen_app = backend_dir / 'generated_app.py'
    if gen_app.exists():
        content_files.append(gen_app.read_text(encoding='utf-8'))
    assert content_files, 'No backend implementation files found'
    combined = '\n'.join(content_files)
    assert '{model_name}' not in combined
    assert 'minimax/minimax-12b-chat' in combined
    assert '5001' in combined
    # Validate docker-compose substitutions
    dc_file = app_dir / 'docker-compose.yml'
    if dc_file.exists():
        dc = dc_file.read_text(encoding='utf-8')
        assert '{backend_port}' not in dc
        assert '5001:5001' in dc
        assert '8001:8001' in dc
