"""Test script for generation_v2 package.

Run from project root:
    python -m pytest tests/unit/test_generation_v2.py -v
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

# Test config
def test_generation_config_basic():
    """Test GenerationConfig creation."""
    from app.services.generation_v2 import GenerationConfig, GenerationMode
    
    config = GenerationConfig(
        model_slug="anthropic_claude-3-5-haiku",
        template_slug="crud_todo_list",
        app_num=1,
    )
    
    assert config.model_slug == "anthropic_claude-3-5-haiku"
    assert config.template_slug == "crud_todo_list"
    assert config.app_num == 1
    assert config.mode == GenerationMode.GUARDED
    assert config.is_guarded is True
    assert config.safe_model_slug == "anthropic_claude-3-5-haiku"


def test_generation_config_unguarded():
    """Test unguarded mode config."""
    from app.services.generation_v2 import GenerationConfig, GenerationMode
    
    config = GenerationConfig(
        model_slug="openai_gpt-4o",
        template_slug="social_blog_posts",
        app_num=2,
        mode=GenerationMode.UNGUARDED,
    )
    
    assert config.is_guarded is False
    assert config.mode == GenerationMode.UNGUARDED


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
    from app.services.generation_v2 import GenerationMode
    
    manager = ScaffoldingManager()
    
    guarded_dir = manager.get_scaffolding_dir(GenerationMode.GUARDED)
    unguarded_dir = manager.get_scaffolding_dir(GenerationMode.UNGUARDED)
    
    assert "react-flask" in str(guarded_dir)
    assert "react-flask-unguarded" in str(unguarded_dir)


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
def test_code_merger_extract_jsx(tmp_path):
    """Test JSX extraction from generated content."""
    from app.services.generation_v2 import CodeMerger
    
    merger = CodeMerger(tmp_path)
    
    content = '''
Here is the React component:

```jsx:App.jsx
function App() {
  return <div>Hello</div>;
}
export default App;
```
'''
    
    blocks = merger._extract_all_code_blocks(content)
    assert len(blocks) >= 1
    jsx_block = next((b for b in blocks if b['language'] == 'jsx'), None)
    assert jsx_block is not None
    assert "function App()" in jsx_block['code']
    assert "export default App" in jsx_block['code']


@pytest.mark.unit
def test_code_merger_extract_css(tmp_path):
    """Test CSS extraction from generated content."""
    from app.services.generation_v2 import CodeMerger
    
    merger = CodeMerger(tmp_path)
    
    content = '''
And the styles:

```css
.container {
  padding: 20px;
}
```
'''
    
    blocks = merger._extract_all_code_blocks(content)
    css_block = next((b for b in blocks if b['language'] == 'css'), None)
    assert css_block is not None
    assert ".container" in css_block['code']


@pytest.mark.unit
def test_code_merger_clean_python(tmp_path):
    """Test Python code cleanup (deduplication)."""
    from app.services.generation_v2 import CodeMerger
    
    merger = CodeMerger(tmp_path)
    
    code = '''import os
import sys
import os
from flask import Flask
from flask import Flask

def main():
    pass
'''
    
    cleaned = merger._clean_python(code)
    assert cleaned.count("import os") == 1
    assert cleaned.count("from flask import Flask") == 1
    assert "def main():" in cleaned


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
