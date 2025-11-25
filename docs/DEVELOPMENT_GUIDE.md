# Development Guide

## Setting Up Your Environment

1.  **VS Code**: Recommended editor. Open the workspace file if available.
2.  **Extensions**: Python, Pylance, Docker, Remote - Containers.
3.  **Virtual Environment**:
    ```bash
    python -m venv .venv
    .venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    ```

## Workflow

### Running Tests
Use the VS Code Test Explorer or the provided tasks:
- **Unit Tests**: `pytest -m "not integration"` (Fast)
- **Integration Tests**: `pytest -m integration` (Slower, requires DB/Docker)
- **Smoke Tests**: `pytest tests/smoke` (Health check)

### Code Style
- **Linting**: Pylint/Flake8 (configured in `.vscode/settings.json`)
- **Formatting**: Black/Isort

### Adding a New Feature

1.  **Backend**:
    - Add models in `src/app/models/`.
    - Create services in `src/app/services/`.
    - Add routes in `src/app/routes/`.
2.  **Frontend**:
    - Add templates in `src/templates/`.
    - Use HTMX for dynamic interactions.
3.  **Migration**:
    - If modifying DB models, generate migration: `flask db migrate`.
    - Apply: `flask db upgrade`.

## Analyzer Development

The analyzer system is modular. To add a new tool:

1.  **Choose Service**: Decide if it fits in static, dynamic, or performance analyzer.
2.  **Implement Tool**: Add tool logic in `analyzer/services/{service}/tools/`.
3.  **Register**: Update the service's main loop to include the new tool.
4.  **Normalize**: Ensure output matches the standard JSON schema.

## Debugging

- **Flask**: Set breakpoints in VS Code and attach to the running process (port 5000).
- **Analyzers**: Use `docker logs <container_id>` or `./start.ps1 -Mode Logs`.
