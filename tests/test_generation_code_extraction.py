"""Test enhanced code extraction and validation fixes."""
import pytest
from pathlib import Path
from src.app.services.generation import CodeMerger


class TestCodeExtraction:
    """Test _select_code_block fence cleanup enhancements."""
    
    @pytest.fixture
    def code_merger(self):
        """Create CodeMerger instance."""
        return CodeMerger()
    
    def test_standard_fence_extraction_python(self, code_merger):
        """Standard case: properly fenced Python code."""
        content = """```python
def hello():
    return "world"
```"""
        result = code_merger._select_code_block(content, {'python', 'py'})
        assert result == 'def hello():\n    return "world"'
    
    def test_standard_fence_extraction_jsx(self, code_merger):
        """Standard case: properly fenced JSX code."""
        content = """```jsx
function App() {
    return <div>Hello</div>;
}
```"""
        result = code_merger._select_code_block(content, {'jsx', 'javascript', 'js'})
        assert result == 'function App() {\n    return <div>Hello</div>;\n}'
    
    def test_incomplete_fence_at_start(self, code_merger):
        """Handles unclosed fence at start (truncation case)."""
        content = """```python
def hello():
    return "world"
# No closing fence - truncated response"""
        result = code_merger._select_code_block(content, {'python', 'py'})
        assert result is not None
        assert 'def hello():' in result
        assert '```python' not in result  # Fence markers should be stripped
    
    def test_incomplete_fence_at_end(self, code_merger):
        """Handles fence markers without opening fence."""
        content = """def hello():
    return "world"
```"""
        result = code_merger._select_code_block(content, {'python', 'py'})
        assert result is not None
        assert 'def hello():' in result
        assert '```' not in result  # Fence markers should be stripped
    
    def test_no_fences_valid_code(self, code_merger):
        """Handles valid code without any fence markers."""
        content = """def hello():
    return "world"
"""
        result = code_merger._select_code_block(content, {'python', 'py'})
        assert result == 'def hello():\n    return "world"'
    
    def test_empty_content(self, code_merger):
        """Handles empty/None content."""
        assert code_merger._select_code_block(None, {'python'}) is None
        assert code_merger._select_code_block('', {'python'}) is None
        assert code_merger._select_code_block('   ', {'python'}) == ''
    
    def test_fence_markers_in_code(self, code_merger):
        """Edge case: fence markers appear in the actual code."""
        content = """```python
# Example showing ``` usage
text = "Use ``` for code blocks"
def hello():
    return text
```"""
        result = code_merger._select_code_block(content, {'python', 'py'})
        assert result is not None
        # The regex extracts the content between fences, which includes the backticks in strings
        assert '# Example showing' in result or 'text = "Use' in result
        assert result.startswith('# Example')  # No leading fence
        assert not result.endswith('```')  # No trailing fence


class TestCodeValidation:
    """Test enhanced validation with fence detection."""
    
    @pytest.fixture
    def code_merger(self):
        """Create CodeMerger instance."""
        return CodeMerger()
    
    def test_valid_python_code(self, code_merger):
        """Valid Python code passes validation."""
        code = """def hello():
    return "world"

if __name__ == "__main__":
    print(hello())
"""
        is_valid, errors = code_merger.validate_generated_code(code, 'backend')
        assert is_valid
        assert len(errors) == 0
    
    def test_invalid_python_syntax(self, code_merger):
        """Invalid Python syntax fails validation."""
        code = """def hello()
    return "world"  # Missing colon
"""
        is_valid, errors = code_merger.validate_generated_code(code, 'backend')
        assert not is_valid
        assert len(errors) > 0
        assert 'syntax error' in errors[0].lower()
    
    def test_fence_markers_in_code_detected(self, code_merger):
        """Detects when code contains fence markers (extraction failure)."""
        code = """```python
def hello():
    return "world"
```"""
        is_valid, errors = code_merger.validate_generated_code(code, 'backend')
        assert not is_valid
        # Should detect fence markers and provide helpful error
        assert any('fence' in err.lower() for err in errors)
    
    def test_empty_code(self, code_merger):
        """Empty code fails validation."""
        is_valid, errors = code_merger.validate_generated_code('', 'backend')
        assert not is_valid
        assert 'empty' in errors[0].lower()
    
    def test_frontend_validation_warnings(self, code_merger):
        """Frontend validation provides warnings for incomplete code."""
        code = """const App = () => {
    return <div>Hello</div>;
}
"""  # Missing export default
        is_valid, errors = code_merger.validate_generated_code(code, 'frontend')
        assert not is_valid
        assert any('export default' in err.lower() for err in errors)
    
    def test_frontend_localhost_warning(self, code_merger):
        """Frontend validation warns about localhost usage."""
        code = """import React from 'react';

const API_URL = 'http://localhost:5000';

function App() {
    return <div>Hello</div>;
}

export default App;
"""
        is_valid, errors = code_merger.validate_generated_code(code, 'frontend')
        assert not is_valid
        assert any('localhost' in err.lower() and 'backend:5000' in err.lower() for err in errors)


class TestIntegration:
    """Integration tests for full extraction + validation flow."""
    
    @pytest.fixture
    def code_merger(self):
        """Create CodeMerger instance."""
        return CodeMerger()
    
    def test_truncated_response_recovery(self, code_merger):
        """Simulates truncated LLM response and validates recovery."""
        # Simulated truncated response (missing closing fence)
        truncated_content = """```python
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
# TRUNCATED - no closing fence"""
        
        # Extraction should handle incomplete fence
        extracted = code_merger._select_code_block(truncated_content, {'python', 'py'})
        assert extracted is not None
        assert 'from flask import Flask' in extracted
        assert '```python' not in extracted
        
        # Validation should pass (valid Python despite missing fence)
        is_valid, errors = code_merger.validate_generated_code(extracted, 'backend')
        assert is_valid or len(errors) == 0  # Should be valid after cleanup
    
    def test_wrong_language_tag(self, code_merger):
        """LLM used wrong language tag (e.g., python for frontend)."""
        content = """```python
function App() {
    return <div>Hello</div>;
}
export default App;
```"""
        
        # Frontend extraction should fall back to first fence
        extracted = code_merger._select_code_block(content, {'jsx', 'javascript', 'js'})
        assert extracted is not None
        assert 'function App()' in extracted
        
        # Validation would fail for backend but that's expected
        # (This tests the fallback logic, not validation)
    
    def test_fence_markers_without_code(self, code_merger):
        """Response has fence markers but no actual code."""
        content = """```python
```"""
        
        extracted = code_merger._select_code_block(content, {'python', 'py'})
        # Should extract empty or minimal content
        assert extracted == '' or extracted is None
