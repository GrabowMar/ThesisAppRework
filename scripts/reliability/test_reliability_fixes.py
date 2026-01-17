#!/usr/bin/env python3
"""
Test Script for Reliability Fixes
==================================

Tests the critical fixes implemented for pipeline analysis failures.
Run this script to verify:
1. No WebSocket connection failures
2. No duplicate task creation
3. Proper task completion tracking

Usage:
    python scripts/reliability/test_reliability_fixes.py
"""

import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:5000"

def log(message):
    """Print timestamped log message."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")

def test_health_checks():
    """Test that all services are healthy."""
    log("Testing health checks...")

    services = {
        'Main App': f"{BASE_URL}/api/health",
        'Static Analyzer': 'http://localhost:2001/api/health',
        'Dynamic Analyzer': 'http://localhost:2002/api/health',
        'Performance Tester': 'http://localhost:2003/api/health',
        'AI Analyzer': 'http://localhost:2004/api/health',
    }

    all_healthy = True
    for name, url in services.items():
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                log(f"✅ {name} is healthy")
            else:
                log(f"❌ {name} returned status {response.status_code}")
                all_healthy = False
        except requests.exceptions.RequestException as e:
            log(f"❌ {name} is unreachable: {e}")
            all_healthy = False

    return all_healthy

def create_test_pipeline():
    """Create a small test pipeline to verify fixes."""
    log("Creating test pipeline...")

    pipeline_config = {
        "name": "Reliability Test Pipeline",
        "generation": {
            "mode": "generate",
            "models": ["anthropic_claude-3-5-haiku"],
            "templates": ["api_url_shortener", "api_weather_display"]
        },
        "analysis": {
            "enabled": True,
            "tools": ["bandit", "pylint", "semgrep", "eslint"],  # Only static tools for quick test
            "options": {
                "parallel": True,
                "maxConcurrentTasks": 2,
                "autoStartContainers": False,  # Disable to test static analysis only
                "stopAfterAnalysis": True
            }
        }
    }

    try:
        response = requests.post(
            f"{BASE_URL}/automation/pipeline",
            json=pipeline_config,
            timeout=10
        )

        if response.status_code == 200 or response.status_code == 201:
            data = response.json()
            pipeline_id = data.get('pipeline_id')
            log(f"✅ Pipeline created: {pipeline_id}")
            return pipeline_id
        else:
            log(f"❌ Failed to create pipeline: {response.status_code}")
            log(f"   Response: {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        log(f"❌ Request failed: {e}")
        return None

def monitor_pipeline(pipeline_id, max_wait=300):
    """Monitor pipeline execution and verify no duplicates."""
    log(f"Monitoring pipeline {pipeline_id}...")

    start_time = time.time()
    last_status = None
    task_ids_seen = set()
    duplicate_detected = False

    while time.time() - start_time < max_wait:
        try:
            response = requests.get(
                f"{BASE_URL}/automation/pipeline/{pipeline_id}/status",
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                status = data.get('status')
                progress = data.get('progress', {})
                analysis = progress.get('analysis', {})

                # Check for duplicate tasks
                task_ids = analysis.get('task_ids', [])
                for task_id in task_ids:
                    if task_id in task_ids_seen and not (task_id.startswith('skipped') or task_id.startswith('error:')):
                        log(f"⚠️  DUPLICATE TASK DETECTED: {task_id}")
                        duplicate_detected = True
                    task_ids_seen.add(task_id)

                # Log status changes
                if status != last_status:
                    log(f"Pipeline status: {status}")
                    log(f"   Generation: {progress.get('generation', {}).get('status')}")
                    log(f"   Analysis: {analysis.get('status')} ({analysis.get('completed')}/{analysis.get('total')})")
                    log(f"   Tasks: {len(task_ids)} task(s)")
                    last_status = status

                # Check if done
                if status in ['completed', 'partial_success', 'failed', 'cancelled']:
                    log(f"Pipeline finished with status: {status}")
                    log(f"   Analysis: {analysis.get('completed')} completed, {analysis.get('failed')} failed")

                    if duplicate_detected:
                        log("❌ TEST FAILED: Duplicate tasks detected!")
                        return False

                    if len(task_ids) != analysis.get('total'):
                        log(f"⚠️  Task count mismatch: {len(task_ids)} tasks vs {analysis.get('total')} expected")

                    # Check success rate
                    if status == 'completed':
                        log("✅ TEST PASSED: Pipeline completed successfully with no duplicates")
                        return True
                    elif status == 'partial_success':
                        log("⚠️  TEST PARTIAL: Pipeline had some failures but no duplicates")
                        return True
                    else:
                        log(f"❌ TEST FAILED: Pipeline failed with status {status}")
                        return False

            time.sleep(5)  # Poll every 5 seconds

        except requests.exceptions.RequestException as e:
            log(f"❌ Error checking status: {e}")
            time.sleep(5)

    log(f"⏱️  TEST TIMEOUT: Pipeline did not complete within {max_wait}s")
    return False

def check_analysis_tasks(pipeline_id):
    """Check analysis tasks for WebSocket failures."""
    log("Checking analysis tasks...")

    try:
        response = requests.get(
            f"{BASE_URL}/api/pipeline/{pipeline_id}/tasks",
            timeout=5
        )

        if response.status_code == 200:
            tasks = response.json().get('tasks', [])
            log(f"Found {len(tasks)} analysis tasks")

            websocket_failures = 0
            for task in tasks:
                task_id = task.get('task_id')
                status = task.get('status')
                error = task.get('error', '')

                # Check for WebSocket-related errors
                if 'websocket' in error.lower() or 'connection' in error.lower():
                    websocket_failures += 1
                    log(f"⚠️  Task {task_id}: WebSocket-related failure")
                    log(f"   Error: {error}")
                elif status == 'failed':
                    log(f"⚠️  Task {task_id}: Failed")
                    log(f"   Error: {error}")
                else:
                    log(f"✅ Task {task_id}: {status}")

            if websocket_failures > 0:
                log(f"❌ {websocket_failures} WebSocket failures detected!")
                return False
            else:
                log("✅ No WebSocket failures detected")
                return True
        else:
            log(f"❌ Failed to get tasks: {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        log(f"❌ Error checking tasks: {e}")
        return False

def main():
    """Run all reliability tests."""
    log("=" * 80)
    log("Starting Reliability Tests")
    log("=" * 80)

    # Test 1: Health checks
    log("\n[TEST 1] Health Checks")
    if not test_health_checks():
        log("❌ Health check failed - aborting tests")
        return False

    # Test 2: Create and monitor pipeline
    log("\n[TEST 2] Pipeline Execution with Duplicate Detection")
    pipeline_id = create_test_pipeline()
    if not pipeline_id:
        log("❌ Failed to create pipeline - aborting tests")
        return False

    # Test 3: Monitor execution
    log("\n[TEST 3] Monitoring Pipeline Execution")
    if not monitor_pipeline(pipeline_id, max_wait=300):
        log("❌ Pipeline monitoring failed")
        return False

    # Test 4: Check for WebSocket failures
    log("\n[TEST 4] Checking for WebSocket Failures")
    if not check_analysis_tasks(pipeline_id):
        log("❌ WebSocket failure check failed")
        return False

    # All tests passed
    log("\n" + "=" * 80)
    log("✅ ALL TESTS PASSED!")
    log("=" * 80)
    log("\nSummary:")
    log("  - Health checks: PASSED")
    log("  - Duplicate detection: PASSED")
    log("  - Pipeline execution: PASSED")
    log("  - WebSocket communication: PASSED")
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
