"""Smoke test: Quick analyzer service health checks."""

import asyncio
import json
import pytest
import websockets

pytestmark = [pytest.mark.smoke, pytest.mark.analyzer]


@pytest.mark.asyncio
async def test_static_analyzer_health():
    """Quick health check for static analyzer service (port 2001)."""
    async with websockets.connect('ws://localhost:2001') as ws:
        await ws.send(json.dumps({'type': 'health_check'}))
        response = await ws.recv()
        data = json.loads(response)
        
        assert data['status'] == 'healthy'
        assert data['service'] == 'static-code-quality-analyzer'
        assert 'available_tools' in data
        assert len(data['available_tools']) > 0


@pytest.mark.asyncio
async def test_dynamic_analyzer_health():
    """Quick health check for dynamic analyzer service (port 2002)."""
    async with websockets.connect('ws://localhost:2002') as ws:
        await ws.send(json.dumps({'type': 'health_check'}))
        response = await ws.recv()
        data = json.loads(response)
        
        assert data['status'] == 'healthy'
        assert 'service' in data
        assert 'available_tools' in data


@pytest.mark.asyncio
async def test_performance_analyzer_health():
    """Quick health check for performance analyzer service (port 2003)."""
    async with websockets.connect('ws://localhost:2003') as ws:
        await ws.send(json.dumps({'type': 'health_check'}))
        response = await ws.recv()
        data = json.loads(response)
        
        assert data['status'] == 'healthy'
        assert 'service' in data


@pytest.mark.asyncio
async def test_ai_analyzer_health():
    """Quick health check for AI analyzer service (port 2004)."""
    async with websockets.connect('ws://localhost:2004') as ws:
        await ws.send(json.dumps({'type': 'health_check'}))
        response = await ws.recv()
        data = json.loads(response)
        
        assert data['status'] == 'healthy'
        assert 'service' in data
