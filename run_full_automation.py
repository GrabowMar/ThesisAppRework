#!/usr/bin/env python
"""
Full automation test script: Generation -> Analysis -> Reports
Tests the entire workflow using API endpoints.
"""

import requests
import json
import time
from datetime import datetime

API_BASE = "http://localhost:5000"
TOKEN = "a_S4ACkLNzuy2U4enBDinjWsDf423gnOQjcADKON_3e5TT8VxSCsVBSTG-zZbz-Z"
OUTPUT_FILE = "c:/Users/grabowmar/Desktop/ThesisAppRework/full_automation_results.json"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# Configuration for the test
MODELS = [
    "google/gemma-3-4b-it",
    "meta-llama/llama-3.2-3b-instruct", 
    "cohere/command-r7b-12-2024"
]

TEMPLATES = [
    "crud_todo_list",
    "auth_user_login",
    "api_weather_display"
]

results = {
    "start_time": "",
    "end_time": "",
    "tests": [],
    "summary": {
        "generation": {"total": 0, "success": 0, "failed": 0},
        "analysis": {"total": 0, "success": 0, "failed": 0},
        "reports": {"total": 0, "success": 0, "failed": 0}
    },
    "apps_generated": [],
    "analysis_tasks": [],
    "reports": []
}

def log(msg, level="INFO"):
    """Log message with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = {
        "timestamp": timestamp,
        "level": level,
        "message": msg
    }
    results["tests"].append(log_entry)
    print(f"[{timestamp}] {level}: {msg}")

def check_analyzer_health():
    """Check if analyzer containers are healthy."""
    log("Checking analyzer container health...")
    try:
        r = requests.get(f"{API_BASE}/automation/api/analyzer/status", headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            healthy = data.get("status", {}).get("overall_healthy", False)
            log(f"Analyzer status: {'HEALTHY' if healthy else 'NOT HEALTHY'}")
            return healthy
        else:
            log(f"Failed to check analyzer status: {r.status_code}", "ERROR")
            return False
    except Exception as e:
        log(f"Error checking analyzer health: {e}", "ERROR")
        return False

def generate_app(model_slug, template_slug):
    """Generate a single application."""
    log(f"Generating app: model={model_slug}, template={template_slug}")
    
    payload = {
        "model_slug": model_slug,
        "template_slug": template_slug,
        "generate_frontend": True,
        "generate_backend": True
    }
    
    results["summary"]["generation"]["total"] += 1
    
    try:
        r = requests.post(
            f"{API_BASE}/api/gen/generate",
            headers=headers,
            json=payload,
            timeout=300  # 5 minutes for generation
        )
        
        if r.status_code == 200:
            data = r.json().get("data", {})
            if data.get("success"):
                # Try multiple ways to get app_number
                app_number = data.get("app_number") or data.get("app_num")
                
                # Fallback: extract from app_dir path (e.g., ".../app3" -> 3)
                if app_number is None and data.get("app_dir"):
                    import re
                    match = re.search(r'app(\d+)$', data.get("app_dir", ""))
                    if match:
                        app_number = int(match.group(1))
                
                app_info = {
                    "model_slug": model_slug,
                    "template": template_slug,
                    "app_id": data.get("app_id") or data.get("database_application_id"),
                    "app_number": app_number,
                    "status": "success"
                }
                results["apps_generated"].append(app_info)
                results["summary"]["generation"]["success"] += 1
                log(f"Generation successful: app{app_number}")
                return app_info
            else:
                error = data.get("error", "Unknown error")
                log(f"Generation failed: {error}", "ERROR")
                results["summary"]["generation"]["failed"] += 1
                return None
        else:
            log(f"Generation HTTP error: {r.status_code} - {r.text[:200]}", "ERROR")
            results["summary"]["generation"]["failed"] += 1
            return None
            
    except Exception as e:
        log(f"Generation exception: {e}", "ERROR")
        results["summary"]["generation"]["failed"] += 1
        return None

def start_analysis(model_slug, app_number):
    """Start analysis for a generated app."""
    # Normalize model slug
    normalized_slug = model_slug.replace("/", "_")
    
    log(f"Starting analysis: {normalized_slug}/app{app_number}")
    results["summary"]["analysis"]["total"] += 1
    
    payload = {
        "profile": "comprehensive",
        "tools": [],
        "options": {
            "autoStartContainers": True,
            "waitForCompletion": True
        }
    }
    
    try:
        # Use the correct analyze endpoint
        r = requests.post(
            f"{API_BASE}/api/app/{normalized_slug}/{app_number}/analyze",
            headers=headers,
            json=payload,
            timeout=600  # 10 minutes for analysis
        )
        
        if r.status_code == 200:
            data = r.json()
            task_id = data.get("task_id") or data.get("data", {}).get("task_id")
            if task_id:
                task_info = {
                    "model_slug": normalized_slug,
                    "app_number": app_number,
                    "task_id": task_id,
                    "status": "started"
                }
                results["analysis_tasks"].append(task_info)
                results["summary"]["analysis"]["success"] += 1
                log(f"Analysis started: task_id={task_id}")
                return task_info
            else:
                log(f"Analysis started but no task_id returned", "WARN")
                results["summary"]["analysis"]["success"] += 1
                return {"status": "started"}
        else:
            log(f"Analysis HTTP error: {r.status_code} - {r.text[:200]}", "ERROR")
            results["summary"]["analysis"]["failed"] += 1
            return None
            
    except Exception as e:
        log(f"Analysis exception: {e}", "ERROR")
        results["summary"]["analysis"]["failed"] += 1
        return None

def generate_report(model_slug, report_type="model_analysis", format_type="html"):
    """Generate a report for a model after analysis."""
    normalized_slug = model_slug.replace("/", "_")
    
    log(f"Generating {report_type} report for: {normalized_slug}")
    results["summary"]["reports"]["total"] += 1
    
    payload = {
        "report_type": report_type,
        "format": format_type,
        "config": {
            "model_slug": normalized_slug
        },
        "title": f"Automation Report: {normalized_slug}",
        "description": f"Auto-generated report for model {normalized_slug}",
        "expires_in_days": 30
    }
    
    try:
        r = requests.post(
            f"{API_BASE}/api/reports/generate",
            headers=headers,
            json=payload,
            timeout=120  # 2 minutes for report generation
        )
        
        if r.status_code in [200, 201]:
            data = r.json()
            if data.get("success"):
                report_info = data.get("report", {})
                report_entry = {
                    "model_slug": normalized_slug,
                    "report_id": report_info.get("report_id"),
                    "report_type": report_type,
                    "format": format_type,
                    "status": report_info.get("status", "completed"),
                    "title": report_info.get("title")
                }
                results["reports"].append(report_entry)
                results["summary"]["reports"]["success"] += 1
                log(f"Report generated: {report_info.get('report_id')}")
                return report_entry
            else:
                error = data.get("error", "Unknown error")
                log(f"Report generation failed: {error}", "ERROR")
                results["summary"]["reports"]["failed"] += 1
                return None
        else:
            log(f"Report HTTP error: {r.status_code} - {r.text[:200]}", "ERROR")
            results["summary"]["reports"]["failed"] += 1
            return None
            
    except Exception as e:
        log(f"Report exception: {e}", "ERROR")
        results["summary"]["reports"]["failed"] += 1
        return None

def save_results():
    """Save results to file."""
    with open(OUTPUT_FILE, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {OUTPUT_FILE}")

def main():
    results["start_time"] = datetime.now().isoformat()
    log("Starting full automation test")
    log(f"Models: {MODELS}")
    log(f"Templates: {TEMPLATES}")
    log(f"Total jobs: {len(MODELS) * len(TEMPLATES)}")
    
    # Step 1: Check analyzer health
    if not check_analyzer_health():
        log("Analyzer not healthy - some tests may fail", "WARN")
    
    # Step 2: Generate applications
    log("=== GENERATION PHASE ===")
    generated_apps = []
    
    for model in MODELS:
        for template in TEMPLATES:
            app_info = generate_app(model, template)
            if app_info:
                generated_apps.append(app_info)
            # Small delay between generations
            time.sleep(2)
    
    log(f"Generation complete: {len(generated_apps)}/{len(MODELS) * len(TEMPLATES)} successful")
    
    # Step 3: Start analysis for each generated app
    log("=== ANALYSIS PHASE ===")
    for app_info in generated_apps:
        start_analysis(
            app_info["model_slug"],
            app_info["app_number"]
        )
        # Small delay between analyses
        time.sleep(5)
    
    # Wait for analyses to complete
    log("Waiting 30 seconds for analysis tasks to complete...")
    time.sleep(30)
    
    # Step 4: Generate reports for each model
    log("=== REPORTS PHASE ===")
    # Get unique models that had successful apps
    unique_models = set()
    for app_info in generated_apps:
        unique_models.add(app_info["model_slug"])
    
    for model_slug in unique_models:
        generate_report(model_slug, "model_analysis", "html")
        time.sleep(2)
    
    # Final summary
    results["end_time"] = datetime.now().isoformat()
    
    log("=== SUMMARY ===")
    log(f"Generation: {results['summary']['generation']['success']}/{results['summary']['generation']['total']} successful")
    log(f"Analysis started: {results['summary']['analysis']['success']}/{results['summary']['analysis']['total']} successful")
    log(f"Reports generated: {results['summary']['reports']['success']}/{results['summary']['reports']['total']} successful")
    
    # Save results
    save_results()
    
    return results

if __name__ == "__main__":
    main()
