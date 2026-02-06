#!/usr/bin/env python3
"""
Batch Analysis Runner
=====================
Orchestrates 100 pipelines (10 models × 10 templates) sequentially.
One model at a time for safety and easier monitoring.
"""

import requests
import time
import json
import sys
import os
import urllib3
from datetime import datetime
from typing import Optional

# Disable SSL warnings for self-signed cert
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
BASE_URL = "https://localhost"  # HTTPS via Nginx
API_URL = f"{BASE_URL}/api/automation/pipelines"
API_TOKEN = os.environ.get("THESIS_API_TOKEN", "r6QP17pZSQ3o-M1bQ64z9tLcHnaVfh_ITMIVB0LFYCf3Y96FS2CjmcvpnJUWHrur")
HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}

# 10 Models (canonical_slug format for database lookup)
# NOTE: First model already completed, starting from model 2
MODELS = [
    # "openai_gpt-5.2-codex-20260114",  # DONE
    "google_gemini-3-pro-preview-20251117",
    "deepseek_deepseek-r1-0528",
    "qwen_qwen3-coder-plus",
    "z-ai_glm-4.7-20251222",
    "openai_gpt-4o-mini",
    "mistralai_mistral-small-3.1-24b-instruct-2503",
    "google_gemini-3-flash-preview-20251217",
    "meta-llama_llama-3.1-405b-instruct",
    "anthropic_claude-4.5-sonnet-20250929",
]

# 10 Templates (first 10 alphabetically)
TEMPLATES = [
    "api_url_shortener",
    "api_weather_display",
    "auth_user_login",
    "booking_reservations",
    "collaboration_simple_poll",
    "content_recipe_list",
    "crm_customer_list",
    "crud_book_library",
    "crud_todo_list",
    "dataviz_sales_table",
]

# Timing
POLL_INTERVAL = 30  # seconds between status checks
MODEL_DELAY = 60    # seconds between models (cooldown)


def log(msg: str, level: str = "INFO"):
    """Print timestamped log message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    icons = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARN": "⚠️", "PROGRESS": "🔄"}
    icon = icons.get(level, "•")
    print(f"[{timestamp}] {icon} {msg}", flush=True)


def start_pipeline(model: str, templates: list[str]) -> Optional[str]:
    """Start a pipeline for one model with all templates."""
    config = {
        "generation": {
            "mode": "generate",
            "models": [model],
            "templates": templates,
        },
        "analysis": {
            "enabled": True,
            "tools": [],  # Empty = all available tools
        },
    }
    
    payload = {
        "name": f"Batch: {model.split('/')[-1]}",
        "config": config,
    }
    
    try:
        resp = requests.post(API_URL, json=payload, headers=HEADERS, timeout=30, verify=False)
        if resp.status_code in (200, 201):
            data = resp.json()
            pipeline_id = data.get("data", {}).get("pipeline_id")
            log(f"Started pipeline {pipeline_id} for {model}", "SUCCESS")
            return pipeline_id
        else:
            log(f"Failed to start pipeline: {resp.status_code} - {resp.text[:200]}", "ERROR")
            return None
    except Exception as e:
        log(f"Error starting pipeline: {e}", "ERROR")
        return None


def get_pipeline_status(pipeline_id: str) -> dict:
    """Get current pipeline status."""
    try:
        resp = requests.get(f"{API_URL}/{pipeline_id}", headers=HEADERS, timeout=15, verify=False)
        if resp.status_code == 200:
            return resp.json().get("data", {})
        return {}
    except Exception as e:
        log(f"Error checking pipeline status: {e}", "WARN")
        return {}


def wait_for_pipeline(pipeline_id: str, model: str) -> bool:
    """Wait for pipeline to complete, return True if successful."""
    start_time = time.time()
    last_progress = ""
    
    while True:
        status_data = get_pipeline_status(pipeline_id)
        status = status_data.get("status", "unknown")
        progress = status_data.get("progress", {})
        
        # Build progress string
        gen_done = progress.get("generation", {}).get("completed", 0)
        gen_total = progress.get("generation", {}).get("total", 0)
        analysis_done = progress.get("analysis", {}).get("completed", 0)
        analysis_total = progress.get("analysis", {}).get("total", 0)
        
        progress_str = f"Gen: {gen_done}/{gen_total}, Analysis: {analysis_done}/{analysis_total}"
        
        if progress_str != last_progress:
            elapsed = int(time.time() - start_time)
            log(f"[{model.split('/')[-1]}] {status.upper()} - {progress_str} ({elapsed}s)", "PROGRESS")
            last_progress = progress_str
        
        if status == "completed":
            elapsed = int(time.time() - start_time)
            log(f"Pipeline completed for {model} in {elapsed}s", "SUCCESS")
            return True
        elif status in ("failed", "cancelled"):
            error = status_data.get("error_message", "Unknown error")
            log(f"Pipeline {status} for {model}: {error}", "ERROR")
            return False
        
        time.sleep(POLL_INTERVAL)


def run_batch():
    """Run all 100 pipelines (10 models × 10 templates)."""
    log("=" * 60)
    log("BATCH ANALYSIS: 10 Models × 10 Templates = 100 Apps")
    log("=" * 60)
    log(f"Models: {len(MODELS)}")
    log(f"Templates: {len(TEMPLATES)}")
    log(f"Total apps to generate and analyze: {len(MODELS) * len(TEMPLATES)}")
    log("")
    
    results = {"success": [], "failed": []}
    overall_start = time.time()
    
    for i, model in enumerate(MODELS, 1):
        log(f"\n{'='*60}")
        log(f"MODEL {i}/{len(MODELS)}: {model}")
        log(f"{'='*60}")
        
        # Start pipeline for this model with all templates
        pipeline_id = start_pipeline(model, TEMPLATES)
        
        if not pipeline_id:
            log(f"Skipping {model} - failed to start pipeline", "ERROR")
            results["failed"].append(model)
            continue
        
        # Wait for pipeline to complete
        success = wait_for_pipeline(pipeline_id, model)
        
        if success:
            results["success"].append(model)
        else:
            results["failed"].append(model)
        
        # Cooldown between models (except last one)
        if i < len(MODELS):
            log(f"Cooldown {MODEL_DELAY}s before next model...", "INFO")
            time.sleep(MODEL_DELAY)
    
    # Final summary
    total_time = int(time.time() - overall_start)
    hours = total_time // 3600
    minutes = (total_time % 3600) // 60
    
    log(f"\n{'='*60}")
    log("BATCH COMPLETE")
    log(f"{'='*60}")
    log(f"Total time: {hours}h {minutes}m")
    log(f"Successful: {len(results['success'])}/{len(MODELS)} models")
    log(f"Failed: {len(results['failed'])}/{len(MODELS)} models")
    
    if results["failed"]:
        log(f"Failed models: {', '.join(results['failed'])}", "ERROR")
    
    # Save results summary
    summary = {
        "completed_at": datetime.now().isoformat(),
        "total_time_seconds": total_time,
        "models": len(MODELS),
        "templates": len(TEMPLATES),
        "total_apps": len(MODELS) * len(TEMPLATES),
        "successful_models": results["success"],
        "failed_models": results["failed"],
    }
    
    with open("batch_results_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    log("Results saved to batch_results_summary.json", "INFO")
    
    return len(results["failed"]) == 0


if __name__ == "__main__":
    try:
        success = run_batch()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        log("\nBatch interrupted by user", "WARN")
        sys.exit(130)
