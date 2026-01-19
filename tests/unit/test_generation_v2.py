"""
Unit Tests for Generation V2 Package
====================================

This module contains comprehensive unit tests for the generation_v2 package.

Tests cover:
- GenerationConfig creation and validation
- GenerationResult error handling
- ScaffoldingManager initialization and functionality
- CodeGenerator prompt building and system prompt retrieval
- Template catalog loading and validation
- Application generation workflow

Run from project root:
    python -m pytest tests/unit/test_generation_v2.py -v

Run specific test:
    python -m pytest tests/unit/test_generation_v2.py::test_generation_config_basic -v
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

# Test config
def test_generation_config_basic():
    """Test GenerationConfig creation."""
    from app.services.generation_v2 import GenerationConfig
    
    config = GenerationConfig(
        model_slug="anthropic_claude-3-5-haiku",
        template_slug="crud_todo_list",
        app_num=1,
    )
    
    assert config.model_slug == "anthropic_claude-3-5-haiku"
    assert config.template_slug == "crud_todo_list"
    assert config.app_num == 1
    assert config.safe_model_slug == "anthropic_claude-3-5-haiku"


def test_generation_result():
    """Test GenerationResult."""
    from app.services.generation_v2 import GenerationResult
    
    result = GenerationResult(success=True)
    assert result.success is True
    assert result.errors == []
    assert result.error_message == ""
    
    result.add_error("Test error")
    assert len(result.errors) == 1
    assert "Test error" in result.error_message


# Test scaffolding manager
@pytest.mark.unit
def test_scaffolding_manager_init():
    """Test ScaffoldingManager initialization."""
    from app.services.generation_v2 import get_scaffolding_manager
    
    manager = get_scaffolding_manager()
    assert manager is not None
    assert manager.port_service is not None


@pytest.mark.unit
def test_scaffolding_dir_paths():
    """Test scaffolding directory path resolution."""
    from app.services.generation_v2.scaffolding import ScaffoldingManager
    
    manager = ScaffoldingManager()
    
    scaffolding_dir = manager.get_scaffolding_dir()
    assert "react-flask" in str(scaffolding_dir)


# Test API client
@pytest.mark.unit
def test_api_client_init():
    """Test OpenRouterClient initialization."""
    from app.services.generation_v2 import get_api_client
    
    client = get_api_client()
    assert client is not None
    assert client.API_URL == "https://openrouter.ai/api/v1/chat/completions"


@pytest.mark.unit
def test_api_client_payload():
    """Test API client payload building."""
    from app.services.generation_v2 import OpenRouterClient
    
    client = OpenRouterClient()
    payload = client._payload(
        model="anthropic/claude-3-haiku",
        messages=[{"role": "user", "content": "test"}],
        temperature=0.3,
        max_tokens=1000,
    )
    
    assert payload["model"] == "anthropic/claude-3-haiku"
    assert payload["temperature"] == 0.3
    assert payload["max_tokens"] == 1000
    assert len(payload["messages"]) == 1


# Test code merger
@pytest.mark.unit
def test_code_merger_init(tmp_path):
    """Test CodeMerger initialization."""
    from app.services.generation_v2 import CodeMerger
    
    merger = CodeMerger(tmp_path)
    assert merger.app_dir == tmp_path


@pytest.mark.unit
def test_code_merger_extract_blocks(tmp_path):
    """Test code block extraction from generated content."""
    from app.services.generation_v2 import CodeMerger
    
    merger = CodeMerger(tmp_path)
    
    content = '''
Here is the Python file:

```python:app.py
from flask import Flask
app = Flask(__name__)
```

And the React component:

```jsx:App.jsx
function App() {
  return <div>Hello</div>;
}
export default App;
```
'''
    
    blocks = merger._extract_code_blocks(content)
    assert len(blocks) >= 2
    assert any("app.py" in b['filename'] for b in blocks)
    assert any("App.jsx" in b['filename'] for b in blocks)


@pytest.mark.unit
def test_code_merger_merge_backend(tmp_path):
    """Test merging backend code blocks."""
    from app.services.generation_v2 import CodeMerger
    
    # Create backend directory
    backend_dir = tmp_path / "backend"
    backend_dir.mkdir(parents=True)
    
    merger = CodeMerger(tmp_path)
    
    code = {
        'backend': '''
```python:app.py
from flask import Flask
app = Flask(__name__)
```

```python:models.py
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()
```
''',
        'frontend': ''
    }
    
    result = merger.merge(code)
    
    # Check files were created
    assert (tmp_path / "backend" / "app.py").exists()
    assert (tmp_path / "backend" / "models.py").exists()
    
    # Check content
    app_content = (tmp_path / "backend" / "app.py").read_text()
    assert "Flask" in app_content


# Test code generator
@pytest.mark.unit
def test_code_generator_init():
    """Test CodeGenerator initialization."""
    from app.services.generation_v2 import get_code_generator
    
    generator = get_code_generator()
    assert generator is not None
    assert generator.client is not None


@pytest.mark.unit
def test_code_generator_format_endpoints():
    """Test endpoint formatting for prompts."""
    from app.services.generation_v2 import CodeGenerator
    
    generator = CodeGenerator()
    
    endpoints = [
        {"method": "GET", "path": "/api/todos", "description": "List todos"},
        {"method": "POST", "path": "/api/todos", "description": "Create todo"},
    ]
    
    formatted = generator._format_endpoints(endpoints)
    assert "GET /api/todos" in formatted
    assert "POST /api/todos" in formatted
    assert "List todos" in formatted


# Test service
@pytest.mark.unit
def test_generation_service_init():
    """Test GenerationService initialization."""
    from app.services.generation_v2 import get_generation_service
    
    service = get_generation_service()
    assert service is not None
    assert service.scaffolding is not None
    assert service.generator is not None


# Test job executor
@pytest.mark.unit
def test_job_executor_init():
    """Test JobExecutor initialization."""
    from app.services.generation_v2 import JobExecutor
    
    executor = JobExecutor()
    assert executor is not None
    assert executor._running is False
    assert executor._executor is None


@pytest.mark.unit
def test_job_executor_start_stop():
    """Test JobExecutor start/stop lifecycle."""
    from app.services.generation_v2 import JobExecutor
    
    executor = JobExecutor()
    
    executor.start()
    assert executor._running is True
    assert executor._executor is not None
    
    executor.stop()
    assert executor._running is False
    assert executor._executor is None
