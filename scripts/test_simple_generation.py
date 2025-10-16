"""Test Script for Simple Generation System

Tests the new simplified generation system to verify it works correctly.

Usage:
    python scripts/test_simple_generation.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import asyncio
from app.services.simple_generation_service import (
    get_simple_generation_service,
    GenerationRequest
)


def test_ports():
    """Test port allocation logic."""
    print("=" * 80)
    print("Testing Port Allocation")
    print("=" * 80)
    
    service = get_simple_generation_service()
    
    test_cases = [
        ("x-ai/grok-code-fast-1", 1),
        ("x-ai/grok-code-fast-1", 2),
        ("openai/gpt-4o", 1),
        ("openai/gpt-4o", 3),
    ]
    
    for model_slug, app_num in test_cases:
        backend, frontend = service.get_ports(model_slug, app_num)
        print(f"{model_slug}/app{app_num}: backend={backend}, frontend={frontend}")
    
    print()


def test_scaffolding():
    """Test scaffolding system."""
    print("=" * 80)
    print("Testing Scaffolding")
    print("=" * 80)
    
    service = get_simple_generation_service()
    
    # Test scaffold
    model_slug = "test-model/test-1"
    app_num = 99
    
    print(f"Scaffolding {model_slug}/app{app_num}...")
    success = service.scaffold_app(model_slug, app_num, force=True)
    
    if success:
        print("✓ Scaffolding successful")
        app_dir = service.get_app_dir(model_slug, app_num)
        
        # Check for key files
        expected_files = [
            "docker-compose.yml",
            "backend/Dockerfile",
            "frontend/Dockerfile",
            "frontend/vite.config.js",
            "frontend/nginx.conf",
        ]
        
        for file_path in expected_files:
            full_path = app_dir / file_path
            if full_path.exists():
                print(f"  ✓ {file_path}")
                
                # Check port substitution in vite.config.js
                if file_path == "frontend/vite.config.js":
                    content = full_path.read_text()
                    backend_port, frontend_port = service.get_ports(model_slug, app_num)
                    if str(frontend_port) in content and str(backend_port) in content:
                        print(f"    ✓ Ports correctly substituted ({backend_port}/{frontend_port})")
                    else:
                        print(f"    ✗ Port substitution failed")
            else:
                print(f"  ✗ {file_path} NOT FOUND")
    else:
        print("✗ Scaffolding failed")
    
    print()


async def test_code_extraction():
    """Test code extraction from AI response."""
    print("=" * 80)
    print("Testing Code Extraction")
    print("=" * 80)
    
    service = get_simple_generation_service()
    
    # Mock AI response with multiple code blocks
    mock_response = """Here's a React frontend:

```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'

export default function App() {
  return (
    <div>
      <h1>Hello World</h1>
    </div>
  )
}
```

```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Test App</title>
</head>
<body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
</body>
</html>
```

```css
body {
  font-family: Arial, sans-serif;
}
```
"""
    
    # Extract blocks
    blocks = service._extract_code_blocks(mock_response)
    print(f"Extracted {len(blocks)} code blocks:")
    for i, (lang, code) in enumerate(blocks, 1):
        print(f"  {i}. {lang} ({len(code)} chars)")
    
    # Test file path determination
    app_dir = Path("generated/apps/test/app1")
    
    print("\nFile path mapping:")
    for lang, code in blocks:
        file_path = service._determine_file_path(app_dir, lang, code, 'frontend')
        if file_path:
            print(f"  {lang} → {file_path.relative_to(app_dir)}")
        else:
            print(f"  {lang} → (not mapped)")
    
    print()


def test_template_loading():
    """Test template loading."""
    print("=" * 80)
    print("Testing Template Loading")
    print("=" * 80)
    
    service = get_simple_generation_service()
    
    # Check for existing templates
    from app.paths import APP_TEMPLATES_DIR
    
    frontend_templates = list(APP_TEMPLATES_DIR.glob("app_*_frontend_*.md"))
    backend_templates = list(APP_TEMPLATES_DIR.glob("app_*_backend_*.md"))
    
    print(f"Found {len(frontend_templates)} frontend templates")
    print(f"Found {len(backend_templates)} backend templates")
    
    if frontend_templates:
        print(f"\nFrontend templates:")
        for t in frontend_templates[:5]:
            print(f"  - {t.name}")
    
    if backend_templates:
        print(f"\nBackend templates:")
        for t in backend_templates[:5]:
            print(f"  - {t.name}")
    
    print()


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("SIMPLE GENERATION SYSTEM - TEST SUITE")
    print("=" * 80 + "\n")
    
    # Run tests
    test_ports()
    test_scaffolding()
    asyncio.run(test_code_extraction())
    test_template_loading()
    
    print("=" * 80)
    print("Test suite complete!")
    print("=" * 80)


if __name__ == '__main__':
    main()
