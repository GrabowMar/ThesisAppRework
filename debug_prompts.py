import sys
import os
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to python path
project_root = os.getcwd()
sys.path.append(os.path.join(project_root, 'src'))

# Mock API client to avoid connection errors during init
with patch('app.services.generation_v2.api_client.get_api_client') as mock_get_client:
    mock_get_client.return_value = MagicMock()
    
    try:
        from app.services.generation_v2.code_generator import CodeGenerator
        generator = CodeGenerator()
        print("CodeGenerator instantiated.")
        
        # Test Data
        reqs = {
            'name': 'Todo App',
            'description': 'A simple todo application',
            'backend_requirements': ['Create todos', 'List todos'],
            'admin_requirements': ['Manage users'],
            'api_endpoints': [{'method': 'GET', 'path': '/api/todos', 'description': 'List todos'}],
            'admin_api_endpoints': [{'method': 'GET', 'path': '/api/admin/users', 'description': 'List users'}],
            'data_model': {'name': 'Todo', 'fields': {'title': 'String', 'done': 'Boolean'}}
        }
        
        # Generate Prompts
        backend_system = generator._get_backend_system_prompt()
        backend_user = generator._build_backend_prompt(reqs)
        
        frontend_system = generator._get_frontend_system_prompt()
        frontend_user = generator._build_frontend_prompt(reqs, "Backend API Context Placeholder")
        
        # Save for analysis
        output_dir = Path("generated_prompts")
        output_dir.mkdir(exist_ok=True)
        
        (output_dir / "backend_system.txt").write_text(backend_system, encoding='utf-8')
        (output_dir / "backend_user.txt").write_text(backend_user, encoding='utf-8')
        (output_dir / "frontend_system.txt").write_text(frontend_system, encoding='utf-8')
        (output_dir / "frontend_user.txt").write_text(frontend_user, encoding='utf-8')
        
        print(f"Prompts saved to {output_dir.absolute()}")
        
        # Quick Analysis
        print("\n--- Analysis ---")
        print(f"Backend System Length: {len(backend_system.splitlines())} lines")
        print(f"Backend User Length: {len(backend_user.splitlines())} lines")
        print(f"Frontend System Length: {len(frontend_system.splitlines())} lines")
        print(f"Frontend User Length: {len(frontend_user.splitlines())} lines")
        
        if "COMPLETE WORKING EXAMPLE STRUCTURE" in backend_system:
            print("Backend System: Structure header present.")
        
        if "skeletal" in backend_user.lower() or "skeleton" in backend_user.lower():
             print("Backend User: References skeleton.")
             
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
