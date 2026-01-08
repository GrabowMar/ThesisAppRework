#!/usr/bin/env python3
"""Patch dashboard_service.py to add Docker-aware analyzer connectivity."""

import sys

# The new function with Docker detection
NEW_FUNCTION = '''def _analyzer_statuses() -> List[ComponentStatus]:
    """Check analyzer service connectivity.
    
    In Docker environments, each analyzer runs in its own container with its own hostname.
    The service key (e.g., 'static-analyzer') matches the Docker service name.
    """
    services = [
        {"key": "static-analyzer", "label": "Static Analyzer", "port": 2001},
        {"key": "dynamic-analyzer", "label": "Dynamic Analyzer", "port": 2002},
        {"key": "performance-tester", "label": "Performance Tester", "port": 2003},
        {"key": "ai-analyzer", "label": "AI Analyzer", "port": 2004},
    ]
    timeout = float(current_app.config.get("DASHBOARD_ANALYZER_TIMEOUT", 2.0))
    
    import os
    # Check if we're in Docker by looking for common Docker environment indicators
    in_docker = (
        os.path.exists("/.dockerenv") 
        or os.environ.get("DOCKER_CONTAINER") == "true"
        or os.environ.get("IN_DOCKER") == "true"
    )
    
    # In Docker, use the service name as the host (Docker DNS resolution)
    # For local dev, use ANALYZER_HOST env var or fallback to localhost
    default_host = os.environ.get("ANALYZER_HOST") or current_app.config.get("DASHBOARD_ANALYZER_HOST", "127.0.0.1")

    results: List[ComponentStatus] = []
    for svc in services:
        port = svc["port"]
        label = svc["label"]
        service_key = svc["key"]
        
        # In Docker, use the service name as host; otherwise use default_host
        if in_docker:
            host = service_key  # e.g., "static-analyzer"
        else:
            host = default_host
        
        try:
            with socket.create_connection((host, port), timeout=timeout):
                results.append(
                    ComponentStatus(
                        key=service_key,
                        label=label,
                        status="healthy",
                        message=f"Port {port} reachable",
                    )
                )
        except OSError as e:
            results.append(
                ComponentStatus(
                    key=service_key,
                    label=label,
                    status="warning",
                    message=f"No response ({host}:{port})",
                )
            )
    return results
'''

filepath = sys.argv[1] if len(sys.argv) > 1 else 'src/app/services/dashboard_service.py'

with open(filepath, 'r') as f:
    content = f.read()

lines = content.split('\n')

# Find start and end of _analyzer_statuses function
start_line = None
end_line = None

for i, line in enumerate(lines):
    if line.strip().startswith('def _analyzer_statuses('):
        start_line = i
    elif start_line is not None and i > start_line:
        # Look for the return statement or next function definition
        if line.strip() == 'return results':
            end_line = i
            break

if start_line is None:
    print("ERROR: Could not find _analyzer_statuses function")
    sys.exit(1)

if end_line is None:
    print("ERROR: Could not find end of _analyzer_statuses function")
    sys.exit(1)

print(f"Found function at lines {start_line + 1} to {end_line + 1}")

# Replace the function
new_lines = lines[:start_line] + NEW_FUNCTION.strip().split('\n') + lines[end_line + 1:]

with open(filepath, 'w') as f:
    f.write('\n'.join(new_lines))

print(f"Patched {filepath} successfully!")
