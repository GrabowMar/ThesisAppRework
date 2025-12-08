#!/usr/bin/env python
"""Test script for automation API endpoints - writes results to file."""

import requests
import json
import time
import sys

API_BASE = "http://localhost:5000"
TOKEN = "8RRBq32-tP0ZyXUc1uCdVd9xmRaCpnbLmkPRd-FagTWZf3lb0JIlT7gSve8NDxEQ"
OUTPUT_FILE = "c:/Users/grabowmar/Desktop/ThesisAppRework/test_results.json"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

results = {"tests": [], "summary": {}}

def log(msg):
    """Log message."""
    results["tests"].append({"log": msg})

def test_analyzer_status():
    """Test analyzer status endpoint."""
    log("Testing Analyzer Status...")
    try:
        r = requests.get(f"{API_BASE}/automation/api/analyzer/status", headers=headers, timeout=30)
        result = {
            "test": "analyzer_status",
            "status_code": r.status_code,
            "response": r.json() if r.status_code == 200 else r.text[:500]
        }
        results["tests"].append(result)
        return r.json() if r.status_code == 200 else {}
    except Exception as e:
        results["tests"].append({"test": "analyzer_status", "error": str(e)})
        return {}

def test_analyzer_health():
    """Test analyzer health endpoint."""
    log("Testing Analyzer Health...")
    try:
        r = requests.get(f"{API_BASE}/automation/api/analyzer/health", headers=headers, timeout=60)
        result = {
            "test": "analyzer_health",
            "status_code": r.status_code,
            "response": r.json() if r.status_code == 200 else r.text[:500]
        }
        results["tests"].append(result)
        return r.json() if r.status_code == 200 else {}
    except Exception as e:
        results["tests"].append({"test": "analyzer_health", "error": str(e)})
        return {}

def test_pipeline_start(models, templates, options):
    """Test starting a pipeline."""
    log("Testing Pipeline Start...")
    payload = {
        "config": {
            "generation": {
                "models": models,
                "templates": templates,
                "options": {}
            },
            "analysis": {
                "enabled": True,
                "profile": "comprehensive",
                "tools": [],
                "options": options
            },
            "reports": {
                "enabled": True,
                "types": ["app_analysis"],
                "format": "html",
                "options": {}
            }
        }
    }
    try:
        r = requests.post(f"{API_BASE}/automation/api/pipeline/start", headers=headers, json=payload, timeout=30)
        result = {
            "test": "pipeline_start",
            "status_code": r.status_code,
            "payload": payload,
            "response": r.json() if r.status_code == 200 else r.text[:500]
        }
        results["tests"].append(result)
        return r.json() if r.status_code == 200 else {}
    except Exception as e:
        results["tests"].append({"test": "pipeline_start", "error": str(e)})
        return {}

if __name__ == "__main__":
    results["start_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
    
    # Test analyzer status
    status = test_analyzer_status()
    
    # Test analyzer health
    health = test_analyzer_health()
    
    # If containers healthy, start the pipeline with 3 models x 3 templates
    if status.get("status", {}).get("overall_healthy", False):
        log("Containers healthy - starting pipeline...")
        models = [
            "google/gemma-3-4b-it",
            "meta-llama/llama-3.2-3b-instruct", 
            "cohere/command-r7b-12-2024"
        ]
        templates = [
            "crud_todo_list",
            "auth_user_login",
            "api_weather_display"
        ]
        pipeline_result = test_pipeline_start(
            models=models,
            templates=templates,
            options={
                "autoStartContainers": True,
                "waitForCompletion": False,  # Don't wait, just start
                "parallel": True
            }
        )
        results["summary"]["pipeline_started"] = pipeline_result.get("success", False)
    else:
        log("Containers not healthy - skipping pipeline test")
        results["summary"]["pipeline_started"] = False
    
    # Summary
    results["summary"]["containers_healthy"] = status.get("status", {}).get("overall_healthy", False)
    results["summary"]["completed"] = True
    results["end_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
    
    # Write results to file
    with open(OUTPUT_FILE, "w") as f:
        json.dump(results, f, indent=2)
    
    # Also try stdout
    print(f"Test complete. Results written to {OUTPUT_FILE}")
