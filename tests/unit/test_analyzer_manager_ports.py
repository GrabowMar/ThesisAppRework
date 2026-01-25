import json
import pytest

from analyzer.analyzer_manager import AnalyzerManager


class DummyManager(AnalyzerManager):
    pass


def test_resolve_app_ports_uses_docker_inspect(monkeypatch, tmp_path):
    mgr = DummyManager()

    # Ensure .env and DB fallback don't return anything
    monkeypatch.setattr(mgr, '_load_port_config', lambda: [])

    # Simulate docker inspect responses for backend and frontend containers
    def fake_run_command(cmd, capture_output=False, timeout=60, cwd=None, env=None):
        # cmd is a list, last arg is container name
        container = cmd[-1]
        if container.endswith('_backend'):
            return 0, json.dumps({"5000/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8005"}]}), ''
        elif container.endswith('_frontend'):
            return 0, json.dumps({"80/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8006"}]}), ''
        return 1, '', 'not found'

    monkeypatch.setattr(mgr, 'run_command', fake_run_command)

    ports = mgr._resolve_app_ports('my_model', 1)

    assert ports == (5000, 80)
