#!/usr/bin/env python3
"""
Pipeline Monitor
================
Real-time terminal dashboard for monitoring batch analysis progress.
Run this in a separate terminal while run_batch_analysis.py is running.
"""

import requests
import time
import sys
import os
import urllib3
from datetime import datetime
from typing import Optional

# Disable SSL warnings for self-signed cert
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
BASE_URL = "https://localhost"
API_URL = f"{BASE_URL}/api/automation/pipelines"
API_TOKEN = os.environ.get("THESIS_API_TOKEN", "r6QP17pZSQ3o-M1bQ64z9tLcHnaVfh_ITMIVB0LFYCf3Y96FS2CjmcvpnJUWHrur")
HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}
REFRESH_INTERVAL = 10  # seconds


def clear_screen():
    """Clear terminal screen."""
    os.system('clear' if os.name != 'nt' else 'cls')


def get_all_pipelines() -> list:
    """Fetch all pipelines from API."""
    try:
        resp = requests.get(API_URL, headers=HEADERS, timeout=15, verify=False)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("data", {}).get("pipelines", data.get("data", []))
        return []
    except Exception as e:
        return []


def get_recent_tasks(limit: int = 20) -> list:
    """Fetch recent analysis tasks."""
    try:
        resp = requests.get(f"{BASE_URL}/api/analysis/tasks?limit={limit}", headers=HEADERS, timeout=15, verify=False)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("data", [])
        return []
    except Exception as e:
        return []


def format_duration(seconds: Optional[int]) -> str:
    """Format seconds as human-readable duration."""
    if seconds is None:
        return "N/A"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


def status_icon(status: str) -> str:
    """Get icon for status."""
    icons = {
        "pending": "⏳",
        "running": "🔄",
        "completed": "✅",
        "failed": "❌",
        "cancelled": "⛔",
    }
    return icons.get(status.lower(), "❓")


def render_dashboard(pipelines: list, tasks: list):
    """Render the monitoring dashboard."""
    clear_screen()
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    print("╔" + "═" * 78 + "╗")
    print("║" + " THESIS APP BATCH ANALYSIS MONITOR ".center(78) + "║")
    print("║" + f" Last updated: {now} ".center(78) + "║")
    print("╠" + "═" * 78 + "╣")
    
    # Summary stats
    total = len(pipelines)
    running = sum(1 for p in pipelines if p.get("status") == "running")
    completed = sum(1 for p in pipelines if p.get("status") == "completed")
    failed = sum(1 for p in pipelines if p.get("status") == "failed")
    pending = sum(1 for p in pipelines if p.get("status") == "pending")
    
    print("║ " + f"Total Pipelines: {total}  |  ⏳ Pending: {pending}  |  🔄 Running: {running}  |  ✅ Completed: {completed}  |  ❌ Failed: {failed}".ljust(77) + "║")
    print("╠" + "═" * 78 + "╣")
    
    # Recent pipelines
    print("║ " + "RECENT PIPELINES".ljust(77) + "║")
    print("╟" + "─" * 78 + "╢")
    
    # Sort by created_at desc
    sorted_pipelines = sorted(
        pipelines, 
        key=lambda x: x.get("created_at", ""), 
        reverse=True
    )[:10]
    
    for p in sorted_pipelines:
        status = p.get("status", "unknown")
        name = p.get("name", "Unnamed")[:30]
        progress = p.get("progress", {})
        
        gen = progress.get("generation", {})
        gen_str = f"{gen.get('completed', 0)}/{gen.get('total', 0)}"
        
        analysis = progress.get("analysis", {})
        analysis_str = f"{analysis.get('completed', 0)}/{analysis.get('total', 0)}"
        
        icon = status_icon(status)
        
        line = f"{icon} {name:<30} | Gen: {gen_str:<6} | Analysis: {analysis_str:<6} | {status.upper()}"
        print("║ " + line.ljust(77) + "║")
    
    if not sorted_pipelines:
        print("║ " + "No pipelines found".center(77) + "║")
    
    print("╠" + "═" * 78 + "╣")
    
    # Running tasks
    print("║ " + "RECENT ANALYSIS TASKS".ljust(77) + "║")
    print("╟" + "─" * 78 + "╢")
    
    running_tasks = [t for t in tasks if t.get("status") in ("running", "pending")][:5]
    completed_tasks = [t for t in tasks if t.get("status") == "completed"][:3]
    
    for t in running_tasks:
        status = t.get("status", "unknown")
        model = t.get("model_slug", "unknown")[:25]
        app_num = t.get("app_number", "?")
        task_type = t.get("analysis_type", "?")[:15]
        icon = status_icon(status)
        
        line = f"{icon} {model}/app{app_num} | {task_type} | {status.upper()}"
        print("║ " + line.ljust(77) + "║")
    
    if completed_tasks:
        print("╟" + "─" * 78 + "╢")
        for t in completed_tasks:
            model = t.get("model_slug", "unknown")[:25]
            app_num = t.get("app_number", "?")
            task_type = t.get("analysis_type", "?")[:15]
            
            line = f"✅ {model}/app{app_num} | {task_type} | COMPLETED"
            print("║ " + line.ljust(77) + "║")
    
    if not tasks:
        print("║ " + "No tasks found".center(77) + "║")
    
    print("╠" + "═" * 78 + "╣")
    
    # Docker stats (optional)
    try:
        import subprocess
        result = subprocess.run(
            ['docker', 'ps', '--filter', 'name=thesisapp-', '--format', '{{.Names}}: {{.Status}}'],
            capture_output=True, text=True, timeout=5
        )
        containers = result.stdout.strip().split('\n')[:5]
        
        print("║ " + "DOCKER CONTAINERS (sample)".ljust(77) + "║")
        print("╟" + "─" * 78 + "╢")
        
        for c in containers:
            if c.strip():
                print("║ " + f"  {c[:75]}".ljust(77) + "║")
    except Exception:
        pass
    
    print("╚" + "═" * 78 + "╝")
    print(f"\nPress Ctrl+C to exit | Refreshing every {REFRESH_INTERVAL}s...")


def main():
    """Main monitoring loop."""
    print("Starting Pipeline Monitor...")
    print("Connecting to API...")
    
    try:
        while True:
            pipelines = get_all_pipelines()
            tasks = get_recent_tasks(20)
            render_dashboard(pipelines, tasks)
            time.sleep(REFRESH_INTERVAL)
    except KeyboardInterrupt:
        print("\n\nMonitor stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
