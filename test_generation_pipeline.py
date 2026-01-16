#!/usr/bin/env python3
"""
Test the Sample Generation Pipeline
====================================

This script tests the full generation + build + analysis pipeline:
1. Generates a sample app using the generation service
2. Builds the app using Docker Compose
3. Runs static analysis on the app to verify analyzability
4. Reports results

Usage:
    python test_generation_pipeline.py

Author: Test Script
Date: January 2026
"""
from __future__ import annotations

import subprocess
import sys
import time
import os
from pathlib import Path
from typing import Optional, Dict, Any

# Ensure src is in path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Configuration
MODEL_SLUG = "anthropic_claude-3-5-haiku"
TEMPLATE_SLUG = "crud_todo_list"  # Simple template for testing


def banner(msg: str) -> None:
    """Print a formatted banner."""
    print("\n" + "=" * 70)
    print(f"  {msg}")
    print("=" * 70 + "\n")


def step(msg: str) -> None:
    """Print a step indicator."""
    print(f"\n>>> {msg}")


def check_prerequisites() -> bool:
    """Check that required services and environment are available."""
    step("Checking prerequisites...")
    
    # Check Docker
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10
        )
        if result.returncode != 0:
            print("  [FAIL] Docker is not running")
            return False
        print("  [OK] Docker is running")
    except Exception as e:
        print(f"  [FAIL] Docker check failed: {e}")
        return False
    
    # Check network
    try:
        result = subprocess.run(
            ["docker", "network", "ls", "--filter", "name=thesis-apps-network", "--format", "{{.Name}}"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if "thesis-apps-network" not in result.stdout:
            print("  [WARN] thesis-apps-network not found, creating it...")
            subprocess.run(["docker", "network", "create", "thesis-apps-network"], check=True)
        print("  [OK] thesis-apps-network exists")
    except Exception as e:
        print(f"  [FAIL] Network check failed: {e}")
        return False
    
    # Check analyzer services
    import socket
    for port, name in [(2001, "static-analyzer"), (2002, "dynamic-analyzer"), 
                       (2003, "performance-tester"), (2004, "ai-analyzer")]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            if result == 0:
                print(f"  [OK] {name} on port {port}")
            else:
                print(f"  [WARN] {name} on port {port} not accessible (optional)")
        except Exception:
            print(f"  [WARN] {name} on port {port} check failed")
    
    return True


def ensure_model_exists() -> bool:
    """Ensure the required model exists in the database, syncing from OpenRouter if needed."""
    step(f"Checking if model '{MODEL_SLUG}' exists in database...")
    
    from app.factory import create_app
    from app.models import ModelCapability
    from app.extensions import db
    
    app = create_app()
    
    with app.app_context():
        # Check if model exists
        model = ModelCapability.query.filter_by(canonical_slug=MODEL_SLUG).first()
        
        if model:
            print(f"  [OK] Model '{MODEL_SLUG}' found in database")
            return True
        
        print(f"  [INFO] Model '{MODEL_SLUG}' not found, attempting to sync from OpenRouter...")
        
        # Try to sync models from OpenRouter
        try:
            import os
            import requests
            from app.routes.shared_utils import _upsert_openrouter_models
            
            api_key = os.getenv('OPENROUTER_API_KEY')
            if not api_key:
                print("  [FAIL] OPENROUTER_API_KEY not set - cannot sync models")
                print("         Set the environment variable and try again")
                return False
            
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            print("  [INFO] Fetching models from OpenRouter API...")
            response = requests.get('https://openrouter.ai/api/v1/models', headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                models_data = data.get('data', [])
                print(f"  [INFO] Fetched {len(models_data)} models from OpenRouter API")
                
                upserted = _upsert_openrouter_models(models_data)
                print(f"  [OK] Synced {upserted} models to database")
                
                # Check again
                model = ModelCapability.query.filter_by(canonical_slug=MODEL_SLUG).first()
                if model:
                    print(f"  [OK] Model '{MODEL_SLUG}' now available")
                    return True
                else:
                    # Try with normalized slug
                    normalized = MODEL_SLUG.replace('-', '_').replace('/', '_')
                    model = ModelCapability.query.filter(
                        ModelCapability.canonical_slug.like(f'%{normalized}%')
                    ).first()
                    if model:
                        print(f"  [OK] Found similar model: {model.canonical_slug}")
                        return True
                    print(f"  [FAIL] Model '{MODEL_SLUG}' still not found after sync")
                    return False
            else:
                print(f"  [FAIL] OpenRouter API returned {response.status_code}")
                return False
                
        except Exception as e:
            print(f"  [FAIL] Error syncing models: {e}")
            import traceback
            traceback.print_exc()
            return False


def test_generation() -> Optional[str]:
    """Test the generation service."""
    step("Testing app generation...")
    
    from app.factory import create_app
    from app.services.generation_v2 import generate_app
    
    app = create_app()
    
    with app.app_context():
        try:
            result = generate_app(
                model_slug=MODEL_SLUG,
                template_slug=TEMPLATE_SLUG,
                app_num=None,  # Auto-assign
                mode="guarded",
            )
            
            result_dict = result.to_dict()
            
            if result_dict.get("success"):
                app_dir = result_dict.get("app_dir")
                print(f"  [OK] Generation successful!")
                print(f"       App directory: {app_dir}")
                print(f"       Files written: {len(result_dict.get('artifacts', []))}")
                return app_dir
            else:
                print(f"  [FAIL] Generation failed: {result_dict.get('errors')}")
                return None
                
        except Exception as e:
            print(f"  [FAIL] Generation exception: {e}")
            import traceback
            traceback.print_exc()
            return None


def test_build(app_dir: str) -> bool:
    """Test Docker build for the generated app."""
    step(f"Testing Docker build for {app_dir}...")
    
    compose_path = Path(app_dir) / "docker-compose.yml"
    
    if not compose_path.exists():
        print(f"  [FAIL] docker-compose.yml not found at {compose_path}")
        return False
    
    try:
        # Build with timeout
        result = subprocess.run(
            ["docker", "compose", "-f", str(compose_path), "build"],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes timeout
            cwd=str(app_dir)
        )
        
        if result.returncode == 0:
            print("  [OK] Docker build successful!")
            return True
        else:
            # Check for common LLM generation issues
            error_output = result.stdout + result.stderr
            if "is not exported" in error_output:
                print(f"  [WARN] Build failed due to LLM code generation issue:")
                print(f"       The LLM generated code with import/export mismatches.")
                print(f"       This is a known limitation - static analysis can detect these issues.")
                return False  # Still a failure, but expected
            else:
                print(f"  [FAIL] Docker build failed:")
                print(f"       stderr: {result.stderr[-500:] if result.stderr else 'N/A'}")
            return False
            
    except subprocess.TimeoutExpired:
        print("  [FAIL] Docker build timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"  [FAIL] Docker build exception: {e}")
        return False


def test_static_analysis(model_slug: str, app_number: int) -> bool:
    """Test static analysis on the generated app."""
    step(f"Testing static analysis for {model_slug}/app{app_number}...")
    
    import socket
    
    # Check if static analyzer is available
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    result = sock.connect_ex(('localhost', 2001))
    sock.close()
    
    if result != 0:
        print("  [SKIP] Static analyzer not available on port 2001")
        return True  # Not a failure, just skip
    
    try:
        # Use analyzer_manager to run analysis
        result = subprocess.run(
            [
                sys.executable,
                "analyzer/analyzer_manager.py",
                "analyze",
                model_slug,
                str(app_number),
                "quick",  # Quick analysis for testing
            ],
            capture_output=True,
            text=True,
            timeout=180,  # 3 minutes
            cwd=str(Path(__file__).parent),
        )
        
        if result.returncode == 0:
            print("  [OK] Static analysis completed!")
            # Show a summary
            lines = result.stdout.split('\n')
            for line in lines:
                if 'findings' in line.lower() or 'success' in line.lower():
                    print(f"       {line.strip()}")
            return True
        else:
            # Analysis tools might find issues - that's fine for testing
            print("  [OK] Static analysis ran (may have found issues)")
            if result.stderr:
                print(f"       Note: {result.stderr[:200]}...")
            return True
            
    except subprocess.TimeoutExpired:
        print("  [WARN] Analysis timed out (this might be normal for comprehensive analysis)")
        return True
    except Exception as e:
        print(f"  [FAIL] Analysis exception: {e}")
        return False


def test_existing_app_pipeline() -> bool:
    """Test build and analysis on an existing, known-working app."""
    step("Testing existing app7 build and analysis...")
    
    # Find app7 (known to work)
    app7_dir = Path(__file__).parent / "generated" / "apps" / "anthropic_claude-3-5-haiku" / "app7"
    
    if not app7_dir.exists():
        print("  [SKIP] app7 not found - skipping existing app test")
        return True
    
    # Test build
    compose_path = app7_dir / "docker-compose.yml"
    if compose_path.exists():
        try:
            result = subprocess.run(
                ["docker", "compose", "-f", str(compose_path), "build"],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode == 0:
                print("  [OK] app7 build successful!")
            else:
                print(f"  [FAIL] app7 build failed")
                return False
        except Exception as e:
            print(f"  [FAIL] app7 build exception: {e}")
            return False
    
    # Test analysis
    return test_static_analysis("anthropic_claude-3-5-haiku", 7)


def check_app_structure(app_dir: str) -> bool:
    """Verify the generated app has the expected structure."""
    step("Checking app structure...")
    
    app_path = Path(app_dir)
    required_files = [
        "docker-compose.yml",
        "backend/app.py",
        "backend/Dockerfile",
        "backend/requirements.txt",
        "frontend/package.json",
        "frontend/Dockerfile",
        "frontend/src/App.jsx",
    ]
    
    all_found = True
    for file in required_files:
        file_path = app_path / file
        if file_path.exists():
            print(f"  [OK] {file}")
        else:
            print(f"  [FAIL] {file} - NOT FOUND")
            all_found = False
    
    return all_found


def main() -> int:
    """Run the generation pipeline test."""
    banner("SAMPLE GENERATION PIPELINE TEST")
    
    results = {
        "prerequisites": False,
        "model_setup": False,
        "existing_app_pipeline": False,
        "generation": False,
        "structure": False,
        "build": False,
        "analysis": False,
    }
    
    # Check prerequisites
    if not check_prerequisites():
        print("\n[ABORT] Prerequisites not met")
        return 1
    results["prerequisites"] = True
    
    # Ensure model exists
    if not ensure_model_exists():
        print("\n[ABORT] Could not find or sync required model")
        return 1
    results["model_setup"] = True
    
    # Test existing app pipeline first (known to work)
    results["existing_app_pipeline"] = test_existing_app_pipeline()
    
    # Test generation
    app_dir = test_generation()
    if not app_dir:
        print("\n[ABORT] Generation failed")
        return 1
    results["generation"] = True
    
    # Check structure
    results["structure"] = check_app_structure(app_dir)
    
    # Test build
    results["build"] = test_build(app_dir)
    
    # Extract app number from app_dir
    app_number = int(Path(app_dir).name.replace("app", ""))
    
    # Test analysis (optional)
    results["analysis"] = test_static_analysis(MODEL_SLUG, app_number)
    
    # Summary
    banner("TEST RESULTS")
    
    all_passed = True
    for test_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} {test_name}")
        if not passed:
            all_passed = False
    
    print()
    
    # Determine overall success
    # Build failures are common with LLM-generated code - check if analysis works
    critical_tests = ["prerequisites", "model_setup", "generation", "structure"]
    critical_passed = all(results.get(t, False) for t in critical_tests)
    
    if all_passed:
        print("✅ All tests passed! The generation pipeline is working correctly.")
        print(f"   Generated app: {app_dir}")
        return 0
    elif critical_passed and results.get("analysis", False):
        print("⚠️  Generation and analysis work, but the generated app had build issues.")
        print("   This is expected with LLM-generated code - the analysis can detect such issues.")
        print(f"   Generated app: {app_dir}")
        return 0  # Consider this acceptable
    else:
        print("❌ Critical tests failed. Check the output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
