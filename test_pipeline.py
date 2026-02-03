#!/usr/bin/env python3
"""Test script for the full pipeline: Generation -> Analysis"""

import json
import requests
import time
import sys
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:5000"
API_URL = f"{BASE_URL}/automation/pipelines"

def print_status(message, status="INFO"):
    """Print formatted status message"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{status}] {message}")

def check_services():
    """Check if the main service is accessible"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print_status("Main service is accessible", "SUCCESS")
            return True
    except Exception as e:
        print_status(f"Cannot reach main service: {e}", "ERROR")
        return False
    return False

def get_available_models():
    """Get list of available models from the database"""
    try:
        # Query database directly via Python
        import sqlite3
        db_path = "src/database/app.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT slug, name FROM model_capability WHERE is_active = 1 LIMIT 5")
        models = cursor.fetchall()
        conn.close()

        if models:
            print_status(f"Found {len(models)} available models:", "INFO")
            for slug, name in models:
                print(f"  - {slug}: {name}")
            return [m[0] for m in models]
        else:
            print_status("No active models found in database", "WARNING")
            return []
    except Exception as e:
        print_status(f"Error querying models: {e}", "ERROR")
        # Fallback to common models
        return ["anthropic_claude-3-5-haiku-20241022", "openai_gpt-4o-mini"]

def get_available_templates():
    """Get available templates"""
    # Check common template names
    templates = ["crud_todo_list", "react_spa", "simple_api"]
    print_status(f"Using templates: {', '.join(templates)}", "INFO")
    return templates

def start_pipeline(model_slugs, template_slug="crud_todo_list"):
    """Start a full pipeline with generation and analysis"""

    pipeline_config = {
        "name": f"Test Pipeline - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "config": {
            "generation": {
                "mode": "generate",
                "models": model_slugs,
                "templates": [template_slug],
                "options": {
                    "parallel": False,  # Sequential for testing
                    "maxConcurrentTasks": 1
                }
            },
            "analysis": {
                "enabled": True,
                "tools": [
                    "bandit",
                    "semgrep",
                    "eslint",
                    "zap",
                    "locust"
                ],
                "options": {
                    "parallel": True,
                    "maxConcurrentTasks": 2,
                    "autoStartContainers": True,
                    "stopAfterAnalysis": False
                }
            }
        }
    }

    print_status("=" * 60, "INFO")
    print_status("STARTING FULL PIPELINE TEST", "INFO")
    print_status("=" * 60, "INFO")
    print_status(f"Models: {', '.join(model_slugs)}", "INFO")
    print_status(f"Template: {template_slug}", "INFO")
    print_status("Analysis enabled: YES", "INFO")
    print_status("Tools: bandit, semgrep, eslint, zap, locust", "INFO")
    print_status("=" * 60, "INFO")

    try:
        # Note: This requires authentication. For now, we'll just show the config
        print_status("Pipeline configuration:", "INFO")
        print(json.dumps(pipeline_config, indent=2))

        print_status("\nTo start the pipeline via API, you need to:", "INFO")
        print("1. Authenticate to the web interface")
        print("2. Use the /automation/pipelines endpoint")
        print("3. Or use the web UI at http://localhost:80")

        # Try to make the request anyway
        print_status("\nAttempting to start pipeline via API...", "INFO")
        response = requests.post(
            API_URL,
            json=pipeline_config,
            timeout=30
        )

        if response.status_code == 201:
            result = response.json()
            pipeline_id = result.get('data', {}).get('pipeline_id')
            print_status(f"Pipeline started successfully! ID: {pipeline_id}", "SUCCESS")
            return pipeline_id
        else:
            print_status(f"API returned status {response.status_code}: {response.text}", "WARNING")
            return None

    except requests.exceptions.RequestException as e:
        print_status(f"Request failed: {e}", "ERROR")
        return None

def monitor_pipeline(pipeline_id):
    """Monitor pipeline progress"""
    if not pipeline_id:
        return

    print_status(f"\nMonitoring pipeline {pipeline_id}...", "INFO")

    status_url = f"{API_URL}/{pipeline_id}"
    max_iterations = 300  # 5 minutes max
    iteration = 0

    while iteration < max_iterations:
        try:
            response = requests.get(status_url, timeout=5)
            if response.status_code == 200:
                data = response.json().get('data', {})
                status = data.get('status')
                progress = data.get('progress', {})

                gen_progress = progress.get('generation', {})
                analysis_progress = progress.get('analysis', {})

                print_status(
                    f"Status: {status} | "
                    f"Generation: {gen_progress.get('completed', 0)}/{gen_progress.get('total', 0)} | "
                    f"Analysis: {analysis_progress.get('completed', 0)}/{analysis_progress.get('total', 0)}",
                    "INFO"
                )

                if status in ['COMPLETED', 'FAILED', 'CANCELLED']:
                    print_status(f"Pipeline finished with status: {status}", "SUCCESS" if status == 'COMPLETED' else "WARNING")
                    break

            time.sleep(1)
            iteration += 1

        except Exception as e:
            print_status(f"Error monitoring: {e}", "ERROR")
            time.sleep(1)
            iteration += 1

def main():
    """Main test function"""
    print_status("Starting Pipeline Test", "INFO")
    print_status("=" * 60, "INFO")

    # Step 1: Check services
    if not check_services():
        print_status("Services not ready. Make sure docker compose is running.", "ERROR")
        # Continue anyway to show the configuration

    # Step 2: Get available models and templates
    models = get_available_models()
    templates = get_available_templates()

    if not models:
        print_status("Using fallback models", "WARNING")
        models = ["anthropic_claude-3-5-haiku-20241022"]

    # Step 3: Start pipeline with first model
    pipeline_id = start_pipeline(models[:1], templates[0])

    # Step 4: Monitor progress
    if pipeline_id:
        monitor_pipeline(pipeline_id)
    else:
        print_status("\nPipeline configuration has been displayed above.", "INFO")
        print_status("To test manually:", "INFO")
        print("1. Access the web UI at http://localhost:80")
        print("2. Navigate to the Automation section")
        print("3. Create a new pipeline with the configuration shown above")

if __name__ == "__main__":
    main()
