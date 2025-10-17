# Docker Container Naming Conflict Fix

## Problem
Multiple applications were trying to use the same container names (`/app_backend`, `/app_frontend`), causing conflicts:
```
Error response from daemon: Conflict. The container name "/app_backend" 
is already in use by container "70fe5ca5...". You have to remove (or rename) 
that container to be able to reuse that name.
```

## Root Cause
The `docker-compose.yml` template uses environment variable substitution for container names:
```yaml
container_name: ${PROJECT_NAME:-app}_backend
```

When `PROJECT_NAME` environment variable is not set, it defaults to `app`, causing all applications to use the same container names.

While the Docker Manager code was using the `-p` (project name) flag correctly:
```bash
docker compose -f <path> -p <unique-project-name> up -d
```

This only affects the Docker Compose project namespace, not the actual container names defined inside the `docker-compose.yml` file.

## Solution
Modified `DockerManager._execute_compose_command()` to pass the `PROJECT_NAME` environment variable to the subprocess:

```python
# Pass PROJECT_NAME environment variable to subprocess
# This ensures docker-compose.yml can use ${PROJECT_NAME} for unique container names
import os
env = os.environ.copy()
env['PROJECT_NAME'] = project_name  # e.g., "openai-gpt-4-app1"

result = subprocess.run(
    cmd,
    cwd=cwd,
    capture_output=True,
    text=True,
    timeout=timeout,
    env=env  # <-- Added this
)
```

Now each application gets unique container names:
- `openai-gpt-4-app1_backend`
- `openai-gpt-4-app1_frontend`
- `anthropic-claude-3-sonnet-app2_backend`
- `anthropic-claude-3-sonnet-app2_frontend`

## Additional Improvements

### 1. Enhanced Error Reporting
Improved error message extraction to provide better debugging information:
```python
if not success:
    error_text = result.stderr.strip() if result.stderr.strip() else result.stdout.strip()
    if error_text:
        lines = [l.strip() for l in error_text.splitlines() if l.strip()]
        out['error'] = lines[-1] if lines else f'Command failed with exit code {result.returncode}'
```

### 2. Consistent Exit Code Field
Added `exit_code` field to match what the log modal expects:
```python
out: Dict[str, Any] = {
    'success': success,
    'returncode': result.returncode,
    'exit_code': result.returncode,  # For consistency with log modal
    'stdout': result.stdout,
    'stderr': result.stderr,
    ...
}
```

### 3. Top-Level Error in Build Response
When build or start fails, the error is now properly bubbled up:
```python
merged = {
    'success': build_result.get('success') and up_result.get('success'),
    'build': build_result,
    'up': up_result
}
# Add top-level error if either step failed
if not merged['success']:
    if not build_result.get('success'):
        merged['error'] = build_result.get('error', 'Build failed')
    elif not up_result.get('success'):
        merged['error'] = up_result.get('error', 'Start failed')
```

## Files Modified
- ✅ `src/app/services/docker_manager.py` - Pass PROJECT_NAME env var and improve error messages

## Testing
To verify the fix:
1. Start multiple applications from different models
2. Check container names: `docker ps --format "{{.Names}}"`
3. Each should have unique names based on model slug and app number
4. No more naming conflicts

## Before
```
/app_backend         (conflict!)
/app_frontend        (conflict!)
```

## After
```
openai-gpt-4-app1_backend
openai-gpt-4-app1_frontend
openai-gpt-4-app2_backend
openai-gpt-4-app2_frontend
anthropic-claude-3-sonnet-app1_backend
anthropic-claude-3-sonnet-app1_frontend
```

## Related
This fix works in conjunction with:
- Container Logs Modal (CONTAINER_LOGS_WINDOW.md) - Shows these errors in the UI
- Docker-compose template (misc/scaffolding/react-flask/docker-compose.yml) - Uses ${PROJECT_NAME}
