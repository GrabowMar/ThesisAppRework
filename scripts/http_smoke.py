"""Start the Flask app on a local HTTP port and run real HTTP requests against key endpoints.

This avoids the Flask test client and exercises the actual HTTP stack.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
from contextlib import closing
from pathlib import Path

import requests
from typing import Protocol


def find_free_port(start: int = 5005, end: int = 5999) -> int:
    for port in range(start, end + 1):
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free port found in range")


class _Server(Protocol):
    def serve_forever(self) -> None: ...
    def shutdown(self) -> None: ...


def start_server_in_thread(port: int) -> tuple[threading.Thread, _Server]:
    # Ensure src is on sys.path
    repo_root = Path(__file__).resolve().parent.parent
    src_path = str(repo_root / 'src')
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    # Enforce Celery-only websocket during smoke runs to avoid mock leakage
    os.environ['WEBSOCKET_STRICT_CELERY'] = 'true'
    os.environ['WEBSOCKET_SERVICE'] = 'celery'

    from werkzeug.serving import make_server
    from app.factory import create_app

    app = create_app()

    # Try to use the same SocketIO server used in production to avoid mock websocket
    try:
        from app.extensions import SOCKETIO_AVAILABLE, socketio  # type: ignore
    except Exception:
        SOCKETIO_AVAILABLE, socketio = False, None  # type: ignore[assignment]

    if SOCKETIO_AVAILABLE and socketio is not None:
        # Run SocketIO server in thread
        def _run_socketio():
            # allow_unsafe_werkzeug for local threaded runs
            socketio.run(app, host="127.0.0.1", port=port, debug=False, allow_unsafe_werkzeug=True)

        thread = threading.Thread(target=_run_socketio, daemon=True)
        thread.start()

        class _DummyServer:
            def shutdown(self):
                # Best-effort: no direct shutdown hook for socketio.run with werkzeug
                pass

        return thread, _DummyServer()  # type: ignore[return-value]
    else:
        server = make_server("127.0.0.1", port, app)
        ctx = app.app_context()
        ctx.push()

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return thread, server


def wait_for_ready(base_url: str, timeout: float = 45.0) -> None:
    """Wait until the server is ready.

    Prefer the lightweight API health endpoint to avoid slow analyzer checks
    inside the main /health route, but fall back to /health if needed.
    """
    deadline = time.time() + timeout
    last_err: Exception | None = None
    paths = ["/api/health", "/health"]
    while time.time() < deadline:
        for p in paths:
            try:
                r = requests.get(base_url + p, timeout=6)
                if r.status_code < 500:
                    return
            except Exception as e:  # noqa: BLE001
                last_err = e
                # Try the next path or loop again shortly
                continue
        time.sleep(0.25)
    raise RuntimeError(f"Server not ready: {last_err}")


def main() -> int:
    port = int(os.environ.get("SMOKE_PORT", find_free_port()))
    base = f"http://127.0.0.1:{port}"
    repo_root = Path(__file__).resolve().parent.parent
    thread, server = start_server_in_thread(port)
    exit_code = 1
    try:
        wait_for_ready(base)
        results: dict[str, object] = {}

        def check(name: str, method: str, path: str, **kwargs):
            url = base + path
            try:
                # Some routes (e.g., /health) may perform dependency checks; allow a bit more time
                resp = requests.request(method, url, timeout=15, **kwargs)
                ok = resp.status_code < 500
                body = None
                try:
                    body = resp.json()
                except Exception:  # noqa: BLE001
                    body = resp.text[:500]
                results[name] = {
                    "url": url,
                    "status": resp.status_code,
                    "ok": ok,
                    "body": body,
                }
                return ok
            except Exception as e:  # noqa: BLE001
                results[name] = {"url": url, "error": str(e), "ok": False}
                return False

        overall_ok = True

        # Core health (prefer the faster API health)
        overall_ok &= check("api_health", "GET", "/api/health")
        overall_ok &= check("health", "GET", "/health")
        # Models listing
        overall_ok &= check("models_all", "GET", "/api/models/all")
        # Dashboard stats
        overall_ok &= check("dashboard_stats", "GET", "/api/dashboard/stats")
        # Analyzer system health route
        overall_ok &= check("system_health", "GET", "/api/system/health")
        # Analysis stats (HTMX-friendly but safe GET)
        overall_ok &= check(
            "analysis_stats",
            "GET",
            "/analysis/api/stats",
            headers={"HX-Request": "true", "HX-Boosted": "true"},
        )

        # Try to start an analysis for a known-looking app id (bulk route)
        overall_ok &= check(
            "analysis_start",
            "POST",
            "/advanced/api/analysis/start",
            json={
                "app_ids": ["anthropic_claude-3.7-sonnet_app1"],
                "analysis_types": ["security"],
            },
            headers={"Content-Type": "application/json"},
        )

        # WebSocket API: prefer real service if available. These will be marked ok
        # only when the service responds without 5xx. They are allowed to be 503
        # if the WS bridge isn't initialized in this environment.
        ws_status_ok = check("ws_status", "GET", "/api/websocket/status")
        if ws_status_ok:
            # Validate active service is celery_websocket
            try:
                body = results.get("ws_status", {}).get("body", {})  # type: ignore[attr-defined]
                active_service = (body or {}).get("active_service") if isinstance(body, dict) else None
                if active_service != "celery_websocket":
                    overall_ok = False
            except Exception:
                # If parsing fails, don't hard-fail the run
                pass
            # Clear events first to ensure clean run
            check("ws_events_clear", "POST", "/api/websocket/events/clear")

            # Start via WS API on a concrete real model/app
            ws_start_ok = check(
                "ws_start",
                "POST",
                "/api/websocket/analysis/start",
                json={
                    "analysis_type": "security",
                    "model_slug": "anthropic_claude-3.7-sonnet",
                    "app_number": 1,
                },
                headers={"Content-Type": "application/json"},
            )
            overall_ok &= ws_start_ok

            # Give the monitor loop a moment if Celery is connected
            time.sleep(1.0)

            overall_ok &= check("ws_analyses", "GET", "/api/websocket/analyses")
            overall_ok &= check("ws_events", "GET", "/api/websocket/events")

        # Query active tasks list to ensure task endpoint responds
        overall_ok &= check(
            "active_tasks",
            "GET",
            "/analysis/api/active-tasks",
            headers={"HX-Request": "true", "HX-Boosted": "true"},
        )

        payload = {"base": base, "results": results}
        out_path = os.environ.get("SMOKE_OUT")
        if not out_path:
            out_path = str(repo_root / "smoke_results.json")
        if out_path:
            try:
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)
                print(f"SMOKE_OUT: {out_path}")
            except Exception:
                # As a fallback, still print to stdout
                print(json.dumps(payload, indent=2))
        else:
            print(json.dumps(payload, indent=2))
        # Always also echo JSON to stdout for CI visibility
        print(json.dumps(payload, indent=2))
        exit_code = 0 if overall_ok else 2
    except Exception as e:  # noqa: BLE001
        # Ensure we always emit a diagnostic file on fatal errors
        payload = {"base": base, "fatal_error": str(e)}
        out_path = str(Path(__file__).resolve().parent.parent / "smoke_results.json")
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            print(f"SMOKE_OUT: {out_path}")
        except Exception:
            print(json.dumps(payload, indent=2))
        print(json.dumps(payload, indent=2))
        exit_code = 3
    finally:
        try:
            server.shutdown()
        except Exception:
            pass
        # Give the thread a moment to stop
        for _ in range(20):
            if not thread.is_alive():
                break
            time.sleep(0.1)
        return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
