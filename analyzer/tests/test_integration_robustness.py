#!/usr/bin/env python3
"""
Integration Tests for Analyzer Robustness
=========================================

Tests the analyzer infrastructure with real Docker services running.
Validates connection pooling, circuit breakers, and task orchestration.
"""

import asyncio
import json
import pytest
import websockets
import time
from datetime import datetime
from typing import Dict, Any

# Test configuration
GATEWAY_URL = "ws://localhost:8765"
STATIC_ANALYZER_URL = "ws://localhost:2001"
DYNAMIC_ANALYZER_URL = "ws://localhost:2002"
AI_ANALYZER_URL = "ws://localhost:2004"


class TestGatewayConnectivity:
    """Test basic gateway connectivity."""

    @pytest.mark.asyncio
    async def test_gateway_connection(self):
        """Gateway accepts connections."""
        try:
            async with websockets.connect(GATEWAY_URL, open_timeout=5) as ws:
                assert ws.open
                print("✓ Gateway connection successful")
        except Exception as e:
            pytest.fail(f"Failed to connect to gateway: {e}")

    @pytest.mark.asyncio
    async def test_gateway_heartbeat(self):
        """Gateway responds to heartbeat/ping."""
        async with websockets.connect(GATEWAY_URL, open_timeout=5) as ws:
            # Send ping
            await ws.send(json.dumps({
                "type": "ping",
                "timestamp": datetime.utcnow().isoformat()
            }))

            # Receive response
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(response)

            assert data.get("type") in ("heartbeat", "pong")
            print(f"✓ Gateway heartbeat response: {data.get('type')}")

    @pytest.mark.asyncio
    async def test_gateway_status_request(self):
        """Gateway responds to status requests."""
        async with websockets.connect(GATEWAY_URL, open_timeout=5) as ws:
            # Send status request
            await ws.send(json.dumps({
                "type": "status_request",
                "id": "test-status-1",
                "timestamp": datetime.utcnow().isoformat()
            }))

            # Receive response
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(response)

            assert data.get("type") == "status_update"
            assert "services" in data.get("data", {})
            print(f"✓ Gateway status: {len(data['data']['services'])} services")


class TestServiceHealthChecks:
    """Test individual service health checks."""

    @pytest.mark.asyncio
    async def test_static_analyzer_health(self):
        """Static analyzer responds to health check."""
        async with websockets.connect(STATIC_ANALYZER_URL, open_timeout=5) as ws:
            await ws.send(json.dumps({
                "type": "health_check",
                "timestamp": datetime.utcnow().isoformat()
            }))

            response = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(response)

            assert data.get("type") == "health_response"
            assert data.get("status") == "healthy"
            assert "available_tools" in data
            print(f"✓ Static analyzer healthy, tools: {data.get('available_tools', [])}")

    @pytest.mark.asyncio
    async def test_dynamic_analyzer_health(self):
        """Dynamic analyzer responds to health check."""
        async with websockets.connect(DYNAMIC_ANALYZER_URL, open_timeout=5) as ws:
            await ws.send(json.dumps({
                "type": "health_check",
                "timestamp": datetime.utcnow().isoformat()
            }))

            response = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(response)

            assert data.get("type") == "health_response"
            assert data.get("status") == "healthy"
            print(f"✓ Dynamic analyzer healthy")

    @pytest.mark.asyncio
    async def test_ai_analyzer_health(self):
        """AI analyzer responds to health check."""
        async with websockets.connect(AI_ANALYZER_URL, open_timeout=5) as ws:
            await ws.send(json.dumps({
                "type": "health_check",
                "timestamp": datetime.utcnow().isoformat()
            }))

            response = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(response)

            assert data.get("type") == "health_response"
            assert data.get("status") == "healthy"
            print(f"✓ AI analyzer healthy")


class TestStreamingCapability:
    """Test that services can stream messages without premature closure."""

    @pytest.mark.asyncio
    async def test_multiple_pings_same_connection(self):
        """Service handles multiple messages on same connection."""
        async with websockets.connect(STATIC_ANALYZER_URL, open_timeout=5) as ws:
            # Send multiple pings
            for i in range(3):
                await ws.send(json.dumps({
                    "type": "ping",
                    "sequence": i,
                    "timestamp": datetime.utcnow().isoformat()
                }))

                response = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(response)
                assert data.get("type") == "pong"
                print(f"✓ Ping {i+1}/3 successful")

            # Connection should still be open
            assert ws.open
            print("✓ Connection remained open for multiple messages")


class TestConcurrentConnections:
    """Test concurrent connection handling."""

    @pytest.mark.asyncio
    async def test_concurrent_health_checks(self):
        """Multiple concurrent health checks succeed."""
        async def health_check(service_url: str, index: int) -> Dict[str, Any]:
            try:
                async with websockets.connect(service_url, open_timeout=10) as ws:
                    await ws.send(json.dumps({
                        "type": "health_check",
                        "index": index,
                        "timestamp": datetime.utcnow().isoformat()
                    }))

                    response = await asyncio.wait_for(ws.recv(), timeout=10)
                    return {"index": index, "success": True, "data": json.loads(response)}
            except Exception as e:
                return {"index": index, "success": False, "error": str(e)}

        # Launch 10 concurrent health checks
        tasks = [
            health_check(STATIC_ANALYZER_URL, i)
            for i in range(10)
        ]

        results = await asyncio.gather(*tasks)

        # All should succeed
        successful = sum(1 for r in results if r["success"])
        assert successful == 10
        print(f"✓ {successful}/10 concurrent health checks succeeded")

    @pytest.mark.asyncio
    async def test_concurrent_gateway_status(self):
        """Gateway handles concurrent status requests."""
        async def gateway_status(index: int) -> Dict[str, Any]:
            try:
                async with websockets.connect(GATEWAY_URL, open_timeout=10) as ws:
                    await ws.send(json.dumps({
                        "type": "status_request",
                        "id": f"concurrent-{index}",
                        "timestamp": datetime.utcnow().isoformat()
                    }))

                    response = await asyncio.wait_for(ws.recv(), timeout=10)
                    return {"index": index, "success": True}
            except Exception as e:
                return {"index": index, "success": False, "error": str(e)}

        # Launch 20 concurrent gateway requests
        tasks = [gateway_status(i) for i in range(20)]
        results = await asyncio.gather(*tasks)

        successful = sum(1 for r in results if r["success"])
        assert successful >= 18  # Allow for some timing variance
        print(f"✓ {successful}/20 concurrent gateway requests succeeded")


class TestErrorHandling:
    """Test error handling and recovery."""

    @pytest.mark.asyncio
    async def test_invalid_message_format(self):
        """Service handles invalid JSON gracefully."""
        async with websockets.connect(STATIC_ANALYZER_URL, open_timeout=5) as ws:
            # Send invalid JSON
            await ws.send("invalid json {]")

            response = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(response)

            assert data.get("type") == "error"
            assert "JSON" in data.get("message", "").upper() or "json" in data.get("message", "")
            print(f"✓ Invalid JSON handled gracefully: {data.get('message')}")

    @pytest.mark.asyncio
    async def test_unknown_message_type(self):
        """Gateway handles unknown message types."""
        async with websockets.connect(GATEWAY_URL, open_timeout=5) as ws:
            # Send unknown message type
            await ws.send(json.dumps({
                "type": "unknown_message_type_xyz",
                "timestamp": datetime.utcnow().isoformat()
            }))

            response = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(response)

            # Should receive error or be ignored
            assert data.get("type") in ("error", "status_update")
            print(f"✓ Unknown message type handled: {data.get('type')}")

    @pytest.mark.asyncio
    async def test_connection_recovery(self):
        """Can reconnect after connection close."""
        # First connection
        async with websockets.connect(STATIC_ANALYZER_URL, open_timeout=5) as ws1:
            await ws1.send(json.dumps({"type": "ping"}))
            response1 = await ws1.recv()
            assert json.loads(response1).get("type") == "pong"
            print("✓ First connection successful")

        # Connection is closed, wait a moment
        await asyncio.sleep(0.5)

        # Second connection should work
        async with websockets.connect(STATIC_ANALYZER_URL, open_timeout=5) as ws2:
            await ws2.send(json.dumps({"type": "ping"}))
            response2 = await ws2.recv()
            assert json.loads(response2).get("type") == "pong"
            print("✓ Reconnection successful")


class TestGatewayEventStreaming:
    """Test gateway event streaming functionality."""

    @pytest.mark.asyncio
    async def test_event_subscription(self):
        """Can subscribe to gateway events."""
        async with websockets.connect(GATEWAY_URL, open_timeout=5) as ws:
            # Subscribe to events
            await ws.send(json.dumps({
                "type": "status_request",
                "data": {
                    "subscribe": "events",
                    "replay": False
                },
                "timestamp": datetime.utcnow().isoformat()
            }))

            # Should receive status update confirming subscription
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(response)

            assert data.get("type") == "status_update"
            assert data.get("data", {}).get("subscribed") is True
            print(f"✓ Event subscription successful")


class TestServiceCapabilities:
    """Test service-specific capabilities."""

    @pytest.mark.asyncio
    async def test_static_analyzer_tools_available(self):
        """Static analyzer reports available tools."""
        async with websockets.connect(STATIC_ANALYZER_URL, open_timeout=5) as ws:
            await ws.send(json.dumps({"type": "health_check"}))
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(response)

            tools = data.get("available_tools", [])
            assert isinstance(tools, list)
            assert len(tools) > 0  # Should have at least some tools

            print(f"✓ Static analyzer tools ({len(tools)}): {', '.join(tools[:5])}")


class TestLoadHandling:
    """Test system behavior under load."""

    @pytest.mark.asyncio
    async def test_rapid_fire_requests(self):
        """System handles rapid sequential requests."""
        async with websockets.connect(GATEWAY_URL, open_timeout=5) as ws:
            success_count = 0

            # Send 50 rapid ping requests
            for i in range(50):
                await ws.send(json.dumps({
                    "type": "ping",
                    "sequence": i
                }))

                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=2)
                    data = json.loads(response)
                    if data.get("type") in ("heartbeat", "pong"):
                        success_count += 1
                except asyncio.TimeoutError:
                    print(f"  Timeout on request {i}")

            # Should handle most requests
            assert success_count >= 45  # Allow for some timing variance
            print(f"✓ Rapid fire: {success_count}/50 requests succeeded")


# Summary test
class TestOverallSystemHealth:
    """Overall system health validation."""

    @pytest.mark.asyncio
    async def test_all_services_healthy(self):
        """All services report healthy status."""
        services = {
            "gateway": GATEWAY_URL,
            "static-analyzer": STATIC_ANALYZER_URL,
            "dynamic-analyzer": DYNAMIC_ANALYZER_URL,
            "ai-analyzer": AI_ANALYZER_URL
        }

        health_status = {}

        for name, url in services.items():
            try:
                if name == "gateway":
                    # Gateway uses status_request
                    async with websockets.connect(url, open_timeout=5) as ws:
                        await ws.send(json.dumps({"type": "status_request"}))
                        response = await asyncio.wait_for(ws.recv(), timeout=5)
                        data = json.loads(response)
                        health_status[name] = "healthy" if data.get("type") == "status_update" else "unhealthy"
                else:
                    # Services use health_check
                    async with websockets.connect(url, open_timeout=5) as ws:
                        await ws.send(json.dumps({"type": "health_check"}))
                        response = await asyncio.wait_for(ws.recv(), timeout=5)
                        data = json.loads(response)
                        health_status[name] = data.get("status", "unknown")
            except Exception as e:
                health_status[name] = f"error: {str(e)}"

        # Print summary
        print("\n" + "="*60)
        print("SYSTEM HEALTH SUMMARY")
        print("="*60)
        for name, status in health_status.items():
            status_icon = "✓" if status == "healthy" else "✗"
            print(f"{status_icon} {name:20s} {status}")
        print("="*60)

        # All should be healthy
        assert all(s == "healthy" for s in health_status.values())


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s", "--tb=short"])
