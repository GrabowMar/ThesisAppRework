#!/usr/bin/env python3
"""
Rerun curl-endpoint-tester for dynamic-success apps.

Workflow per app:
  1) Resolve latest consolidated JSON (manifest.json -> main_result_file).
  2) Start app containers (docker compose up -d) with PROJECT_NAME override so
     dynamic-analyzer can reach {PROJECT_NAME}_backend via thesis-apps-network.
  3) Send dynamic-analyzer request with tools=["curl-endpoint-tester"] and
     config={"template_slug": ...}.
  4) Merge the new curl-endpoint-tester result into the existing consolidated JSON.
  5) Write a new timestamped JSON snapshot + update manifest.json main_result_file.
  6) Update analysis_tasks.result_summary for task_id in instance/app.db.
  7) Stop app containers (docker compose down --remove-orphans).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "results"
GENERATED_DIR = REPO_ROOT / "generated" / "apps"
DB_PATH = REPO_ROOT / "instance" / "app.db"

# Allow importing repo-local packages when executed as scripts/xxx.py
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _safe_model_fs(model_slug: str) -> str:
    return str(model_slug).replace("/", "_").replace("\\", "_")


def _safe_model_docker(model_slug: str) -> str:
    return str(model_slug).replace("/", "-").replace("_", "-").replace(".", "-")


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _pick_main_json(task_dir: Path) -> Optional[Path]:
    manifest = task_dir / "manifest.json"
    if manifest.exists():
        m = _load_json(manifest) or {}
        main = m.get("main_result_file")
        if isinstance(main, str) and main:
            p = task_dir / main
            if p.exists():
                return p

    # Fallback: latest JSON file (exclude manifest.json)
    candidates = [p for p in task_dir.glob("*.json") if p.name != "manifest.json" and p.is_file()]
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.name)
    return candidates[-1]


def _pick_latest_task(app_dir: Path) -> Optional[Tuple[Path, Path]]:
    candidates: List[Tuple[str, Path, Path]] = []
    for task_dir in app_dir.iterdir():
        if not task_dir.is_dir():
            continue
        main_json = _pick_main_json(task_dir)
        if not main_json:
            continue
        ts = ""
        manifest = task_dir / "manifest.json"
        if manifest.exists():
            m = _load_json(manifest) or {}
            ts = str(m.get("timestamp") or "")
        candidates.append((ts, task_dir, main_json))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    _, task_dir, main_json = candidates[-1]
    return task_dir, main_json


def _extract_template_slug(data: Dict[str, Any]) -> Optional[str]:
    ai = (data.get("services") or {}).get("ai-analyzer") or {}
    analysis = ((ai.get("payload") or {}).get("analysis") or {}) if isinstance(ai, dict) else {}
    meta = analysis.get("metadata") or {}
    if isinstance(meta, dict) and meta.get("template_slug"):
        return str(meta["template_slug"])
    tools = analysis.get("tools") or {}
    if isinstance(tools, dict):
        req = tools.get("requirements-scanner") or {}
        if isinstance(req, dict):
            rmeta = req.get("metadata") or {}
            if isinstance(rmeta, dict) and rmeta.get("template_slug"):
                return str(rmeta["template_slug"])
    return None


def _extract_true_app_number(data: Dict[str, Any], fallback: int) -> int:
    for svc in ("static-analyzer", "dynamic-analyzer", "performance-tester", "ai-analyzer"):
        s = (data.get("services") or {}).get(svc) or {}
        analysis = ((s.get("payload") or {}).get("analysis") or {}) if isinstance(s, dict) else {}
        if isinstance(analysis, dict) and isinstance(analysis.get("app_number"), int):
            return int(analysis["app_number"])
    return int(fallback)


def _read_env_ports(app_dir: Path) -> Optional[Tuple[int, int]]:
    env_path = app_dir / ".env"
    if not env_path.exists():
        return None
    backend = frontend = None
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line.startswith("BACKEND_PORT="):
            try:
                backend = int(line.split("=", 1)[1].strip())
            except Exception:
                pass
        if line.startswith("FRONTEND_PORT="):
            try:
                frontend = int(line.split("=", 1)[1].strip())
            except Exception:
                pass
    if backend and frontend:
        return backend, frontend
    return None


def _resolve_generated_app_dir(model_slug: str, app_number: int) -> Optional[Path]:
    base = GENERATED_DIR / model_slug
    direct = base / f"app{app_number}"
    if direct.exists():
        return direct
    if base.exists():
        for template_dir in base.iterdir():
            candidate = template_dir / f"app{app_number}"
            if candidate.exists():
                return candidate
    return None


def _docker_compose_cmd() -> List[str]:
    try:
        r = subprocess.run(["docker", "compose", "version"], capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            return ["docker", "compose"]
    except Exception:
        pass
    return ["docker-compose"]


def _run(cmd: List[str], *, cwd: Optional[Path] = None, env: Optional[Dict[str, str]] = None, timeout: int = 300) -> Tuple[int, str, str]:
    p = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return p.returncode, p.stdout, p.stderr


def _wait_backend_health(backend_port: int, timeout_s: int) -> bool:
    deadline = time.time() + timeout_s
    url = f"http://localhost:{backend_port}/api/health"
    while time.time() < deadline:
        rc, _, _ = _run(["curl", "-sf", "--max-time", "2", url], timeout=10)
        if rc == 0:
            return True
        time.sleep(2)
    return False


def _send_endpoint_scan(model_slug: str, app_number: int, backend_port: int, project_name: str, template_slug: str, timeout_s: int) -> Dict[str, Any]:
    # Defer heavy import until needed (script can still list candidates without websockets installed).
    from analyzer.analyzer_manager import AnalyzerManager

    mgr = AnalyzerManager()
    message = {
        "type": "dynamic_analyze",
        "model_slug": model_slug,
        "app_number": app_number,
        "target_urls": [
            f"http://{project_name}_backend:{backend_port}",
            f"http://{project_name}_frontend:80",
        ],
        "tools": ["curl-endpoint-tester"],
        "config": {"template_slug": template_slug},
        "timestamp": _now_iso(),
        "id": str(uuid.uuid4()),
    }
    return asyncio_run(mgr.send_websocket_message("dynamic-analyzer", message, timeout=timeout_s))


def asyncio_run(coro):
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            # Should not happen in this script, but keep it safe.
            return asyncio.run(coro)
    except RuntimeError:
        pass
    return asyncio.run(coro)


def _extract_curl_payload(frame: Dict[str, Any]) -> Optional[Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]]:
    analysis = frame.get("analysis")
    if not isinstance(analysis, dict):
        # Some frames may wrap analysis differently; keep a safe fallback.
        payload = frame.get("payload")
        if isinstance(payload, dict) and isinstance(payload.get("analysis"), dict):
            analysis = payload["analysis"]
    if not isinstance(analysis, dict):
        return None

    results = analysis.get("results") or {}
    if not isinstance(results, dict):
        return None
    curl = results.get("curl-endpoint-tester")
    if not isinstance(curl, dict):
        return None

    tool_runs = results.get("tool_runs") or {}
    if not isinstance(tool_runs, dict):
        tool_runs = {}
    tr = tool_runs.get("curl-endpoint-tester") if isinstance(tool_runs.get("curl-endpoint-tester"), dict) else {}

    tool_results = analysis.get("tool_results") or {}
    if not isinstance(tool_results, dict):
        tool_results = {}
    ts = tool_results.get("curl-endpoint-tester") if isinstance(tool_results.get("curl-endpoint-tester"), dict) else {}

    return curl, tr, ts


def _merge_curl_into_consolidated(consolidated: Dict[str, Any], curl: Dict[str, Any], tool_run: Dict[str, Any], tool_summary: Dict[str, Any]) -> bool:
    services = consolidated.setdefault("services", {})
    dyn = services.get("dynamic-analyzer")
    if not isinstance(dyn, dict):
        return False
    payload = dyn.get("payload")
    if not isinstance(payload, dict):
        return False
    analysis = payload.get("analysis")
    if not isinstance(analysis, dict):
        return False
    results = analysis.setdefault("results", {})
    if not isinstance(results, dict):
        return False

    results["curl-endpoint-tester"] = curl

    tool_runs = results.setdefault("tool_runs", {})
    if isinstance(tool_runs, dict) and tool_run:
        tool_runs["curl-endpoint-tester"] = tool_run

    tr = analysis.setdefault("tool_results", {})
    if isinstance(tr, dict) and tool_summary:
        tr["curl-endpoint-tester"] = tool_summary

    tools_used = analysis.get("tools_used")
    if isinstance(tools_used, list) and "curl-endpoint-tester" not in tools_used:
        tools_used.append("curl-endpoint-tester")

    return True


def _write_new_snapshot(task_dir: Path, consolidated: Dict[str, Any], model_slug: str, app_number: int) -> str:
    fname = f"{_safe_model_fs(model_slug)}_app{app_number}_{task_dir.name}_{_now_stamp()}.json"
    out_path = task_dir / fname
    out_path.write_text(json.dumps(consolidated, indent=2, default=str) + "\n", encoding="utf-8")

    manifest_path = task_dir / "manifest.json"
    manifest = _load_json(manifest_path) if manifest_path.exists() else {}
    if not isinstance(manifest, dict):
        manifest = {}
    manifest["task_id"] = consolidated.get("task", {}).get("task_id") or manifest.get("task_id") or task_dir.name.replace("task_", "")
    manifest["status"] = manifest.get("status") or "completed"
    manifest["main_result_file"] = fname
    manifest["timestamp"] = _now_iso()
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")
    return fname


def _update_db_result_summary(task_id: str, consolidated: Dict[str, Any]) -> None:
    import sqlite3
    if not DB_PATH.exists():
        return
    con = sqlite3.connect(str(DB_PATH))
    try:
        cur = con.cursor()
        cur.execute(
            "UPDATE analysis_tasks SET result_summary=?, updated_at=? WHERE task_id=?",
            (json.dumps(consolidated, default=str), _now_iso(), task_id),
        )
        con.commit()
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Rerun curl-endpoint-tester for dynamic-success apps")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of apps processed (0 = no limit)")
    parser.add_argument("--start-index", type=int, default=0, help="Skip first N eligible apps (resume helper)")
    parser.add_argument("--health-timeout", type=int, default=120, help="Seconds to wait for backend /api/health")
    parser.add_argument("--scan-timeout", type=int, default=180, help="WebSocket timeout for dynamic-analyzer request")
    args = parser.parse_args()

    if not RESULTS_DIR.exists():
        print(f"ERROR: results dir not found: {RESULTS_DIR}")
        return 2

    compose_cmd = _docker_compose_cmd()
    eligible: List[Tuple[str, int, str, Path, Path]] = []

    for model_dir in sorted(RESULTS_DIR.iterdir()):
        if not model_dir.is_dir():
            continue
        model_slug = model_dir.name
        for app_dir in sorted(model_dir.iterdir()):
            if not app_dir.is_dir():
                continue
            picked = _pick_latest_task(app_dir)
            if not picked:
                continue
            task_dir, main_json = picked
            data = _load_json(main_json)
            if not data:
                continue
            dyn = (data.get("services") or {}).get("dynamic-analyzer") or {}
            if not (isinstance(dyn, dict) and dyn.get("status") == "success"):
                continue

            # Results folders can be misnumbered; prefer app_number from payload.
            m = (data.get("services") or {}).get("static-analyzer") or {}
            analysis = ((m.get("payload") or {}).get("analysis") or {}) if isinstance(m, dict) else {}
            app_num_from_dir = int(re.sub(r"^app", "", app_dir.name) or "0")
            true_app_number = _extract_true_app_number(data, app_num_from_dir)
            task_id = str((data.get("task") or {}).get("task_id") or task_dir.name.replace("task_", ""))
            tpl = _extract_template_slug(data)
            if not tpl:
                continue
            eligible.append((model_slug, true_app_number, tpl, task_dir, main_json))

    eligible.sort(key=lambda x: (x[0], x[1], x[3].name))
    eligible = eligible[args.start_index:]
    if args.limit and args.limit > 0:
        eligible = eligible[: args.limit]

    print(f"Eligible apps (dynamic-success): {len(eligible)}")
    if not eligible:
        return 0

    ok = 0
    updated = 0
    for idx, (model_slug, app_number, template_slug, task_dir, main_json) in enumerate(eligible, start=1):
        print(f"[{idx}/{len(eligible)}] {model_slug} app{app_number} ({template_slug})")

        consolidated = _load_json(main_json)
        if not consolidated:
            print("  - SKIP: cannot load consolidated JSON")
            continue

        gen_app_dir = _resolve_generated_app_dir(model_slug, app_number)
        if not gen_app_dir:
            print("  - SKIP: generated app dir not found")
            continue

        ports = _read_env_ports(gen_app_dir)
        if not ports:
            print("  - SKIP: cannot resolve BACKEND_PORT/FRONTEND_PORT")
            continue
        backend_port, _frontend_port = ports
        compose_path = gen_app_dir / "docker-compose.yml"
        if not compose_path.exists():
            print("  - SKIP: docker-compose.yml not found")
            continue

        build_id = uuid.uuid4().hex[:8]
        project_name = f"{_safe_model_docker(model_slug)}-app{app_number}-{build_id}"
        env = os.environ.copy()
        env["PROJECT_NAME"] = project_name
        env["COMPOSE_PROJECT_NAME"] = project_name

        # Start app containers
        rc, _, err = _run(compose_cmd + ["-f", str(compose_path), "-p", project_name, "up", "-d"], cwd=gen_app_dir, env=env, timeout=600)
        if rc != 0:
            print(f"  - START failed: {err.strip()[:300]}")
            continue

        try:
            healthy = _wait_backend_health(backend_port, timeout_s=args.health_timeout)
            if not healthy:
                print("  - WARN: backend health timeout (still attempting scan)")

            frame = _send_endpoint_scan(model_slug, app_number, backend_port, project_name, template_slug, timeout_s=args.scan_timeout)
            extracted = _extract_curl_payload(frame) if isinstance(frame, dict) else None
            if not extracted:
                print("  - FAIL: no curl-endpoint-tester payload in response")
                continue
            curl, tool_run, tool_summary = extracted

            merged = _merge_curl_into_consolidated(consolidated, curl, tool_run, tool_summary)
            if not merged:
                print("  - FAIL: could not merge into consolidated JSON")
                continue

            _write_new_snapshot(task_dir, consolidated, model_slug, app_number)
            task_id = str((consolidated.get("task") or {}).get("task_id") or task_dir.name.replace("task_", ""))
            _update_db_result_summary(task_id, consolidated)

            updated += 1

            ep = curl.get("endpoint_tests") or {}
            if isinstance(ep, dict):
                passed = ep.get("passed")
                total = ep.get("total")
                if isinstance(passed, int) and isinstance(total, int):
                    print(f"  - OK: endpoints {passed}/{total}")
                    ok += 1
                else:
                    print("  - OK: updated")
            else:
                print("  - OK: updated")

        finally:
            # Always stop containers to save resources
            _run(compose_cmd + ["-f", str(compose_path), "-p", project_name, "down", "--remove-orphans"], cwd=gen_app_dir, env=env, timeout=300)

    print(f"Done. Updated={updated}, OK(endpoints parsed)={ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
