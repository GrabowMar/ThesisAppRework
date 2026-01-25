import asyncio
import json
import os
import pytest

from app.tasks import _run_websocket_sync


class DummyWebsocket:
    def __init__(self):
        self.sent = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def send(self, msg):
        self.sent.append(json.loads(msg))

    async def recv(self):
        await asyncio.sleep(0.01)
        return json.dumps({'type': 'dynamic_analysis_result', 'status': 'success', 'analysis': {}})


class DummyConnect:
    def __init__(self, ws):
        self.ws = ws

    def __call__(self, *args, **kwargs):
        return self.ws


@pytest.mark.asyncio
async def test_run_websocket_sync_uses_container_targets(monkeypatch):
    # Set env to indicate analyzer URLs use container names
    monkeypatch.setenv('DYNAMIC_ANALYZER_URLS', 'ws://dynamic-analyzer:2002')

    # Patch analyzer manager to return ports
    class FakeMgr:
        def _resolve_app_ports(self, model_slug, app_number):
            return (5003, 8003)

        def _is_running_in_docker(self):
            return True

    class Wrapper:
        manager = FakeMgr()

    monkeypatch.setattr('app.tasks.get_analyzer_wrapper', lambda: Wrapper())

    ws = DummyWebsocket()
    monkeypatch.setattr('websockets.connect', DummyConnect(ws))

    # Run synchronous wrapper (it will use our fake websockets and send request)
    result = _run_websocket_sync('dynamic-analyzer', 'anthropic_claude-3-5-haiku', 3, ['curl'], timeout=5)

    # The monkeypatched DummyWebsocket should have captured the sent message
    # but because _run_websocket_sync returns synchronously, ensure ws.sent has at least one message
    assert ws.sent, "No message sent to websocket"

    msg = ws.sent[0]
    assert 'target_urls' in msg
    # Expect container network addresses (container_name with resolved ports)
    assert 'anthropic-claude-3-5-haiku-app3_backend:5003' in msg['target_urls'][0]
    assert 'anthropic-claude-3-5-haiku-app3_frontend:8003' in msg['target_urls'][1]
