#!/usr/bin/env python3
"""Inspect the structure of analysis results."""
import sys
import json
sys.path.insert(0, 'src')

from app import create_app
from app.models import AnalysisTask

app = create_app()
with app.app_context():
    task = AnalysisTask.query.filter_by(task_id='task_c0e7bdb31730').first()
    if not task:
        print("Task not found")
        sys.exit(1)
    
    result = task.get_result_summary()
    services = result.get('services', {})
    
    print("\n" + "="*60)
    print("RESULT STRUCTURE INSPECTION")
    print("="*60)
    
    print("\nTop-level keys:", list(result.keys()))
    
    for service_name, service_data in services.items():
        print(f"\n📦 {service_name}")
        print(f"   Keys: {list(service_data.keys())}")
        print(f"   Status: {service_data.get('status')}")
        
        # Show first 500 chars of data
        data_str = json.dumps(service_data, indent=2)
        if len(data_str) > 1000:
            print(f"   Data preview:\n{data_str[:1000]}...")
        else:
            print(f"   Data:\n{data_str}")
