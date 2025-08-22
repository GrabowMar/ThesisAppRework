#!/usr/bin/env python
"""Build and start an app's backend & frontend containers.

Usage:
  python scripts/build_start_app.py --model anthropic_claude-3.7-sonnet --app 1 [--rebuild]

This script:
 1. Locates the app directory under misc/models/{model}/app{N}
 2. Loads port info from DB if available, else falls back to misc/port_config.json
 3. Ensures docker-compose.yml exists (reports if missing)
 4. Runs `docker compose build` (with optional --no-cache) and `docker compose up -d`

Exits non-zero on failure.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MISC_DIR = PROJECT_ROOT / 'misc'
MODELS_DIR = MISC_DIR / 'models'
PORT_CONFIG_FILE = MISC_DIR / 'port_config.json'
SRC_DIR = PROJECT_ROOT / 'src'

# Optional: access DB to resolve ports if app context available
DB_AVAILABLE = False
try:
    sys.path.insert(0, str(SRC_DIR))
    from app.factory import create_app  # type: ignore
    try:
        from app.models import PortConfiguration  # type: ignore
    except Exception:  # pragma: no cover
        PortConfiguration = None  # type: ignore
    flask_app = create_app()  # may fail if env not configured
    DB_AVAILABLE = True
except Exception:
    DB_AVAILABLE = False

def load_ports(model: str, app_num: int) -> dict:
    if DB_AVAILABLE and PortConfiguration is not None:
        try:
            with flask_app.app_context():  # type: ignore
                pc = PortConfiguration.query.filter_by(model=model, app_num=app_num).first()
                if pc:
                    return {'backend': pc.backend_port, 'frontend': pc.frontend_port}
        except Exception:
            pass
    # Fallback JSON
    if PORT_CONFIG_FILE.exists():
        try:
            data = json.loads(PORT_CONFIG_FILE.read_text())
            key = f"{model}_{app_num}"
            if key in data:
                return data[key]
        except Exception:
            pass
    return {'backend': None, 'frontend': None}

def run(cmd: list[str], cwd: Path) -> int:
    print(f"-> Running: {' '.join(cmd)} (cwd={cwd})")
    proc = subprocess.run(cmd, cwd=cwd)
    return proc.returncode

def main():
    parser = argparse.ArgumentParser(description='Build & start app containers')
    parser.add_argument('--model', required=True, help='Model slug (matches directory name)')
    parser.add_argument('--app', type=int, required=True, help='App number (e.g., 1)')
    parser.add_argument('--rebuild', action='store_true', help='Force no-cache rebuild')
    args = parser.parse_args()

    app_dir = MODELS_DIR / args.model / f"app{args.app}"
    if not app_dir.exists():
        print(f"ERROR: App directory not found: {app_dir}", file=sys.stderr)
        return 2

    compose_file = app_dir / 'docker-compose.yml'
    if not compose_file.exists():
        print(f"ERROR: docker-compose.yml missing in {app_dir}", file=sys.stderr)
        return 3

    ports = load_ports(args.model, args.app)
    print(f"Resolved ports: backend={ports['backend']} frontend={ports['frontend']}")

    build_cmd = ['docker', 'compose', 'build']
    if args.rebuild:
        build_cmd.append('--no-cache')
    rc = run(build_cmd, app_dir)
    if rc != 0:
        return rc

    up_cmd = ['docker', 'compose', 'up', '-d']
    rc = run(up_cmd, app_dir)
    if rc != 0:
        return rc

    print('Success: containers started.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
