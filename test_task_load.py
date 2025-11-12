#!/usr/bin/env python3
"""Test script to verify task data loading."""

import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import AnalysisTask
from app.services.service_locator import ServiceLocator

app = create_app()

with app.app_context():
    # Check database
    task = AnalysisTask.query.filter_by(task_id='task_ed6195726566').first()
    print(f"=== Database Check ===")
    print(f"Task found: {task is not None}")
    if task:
        print(f"Status: {task.status}")
        print(f"Has result_summary: {task.result_summary is not None}")
        print(f"Model: {task.target_model}")
        print(f"App: {task.target_app_number}")
    
    # Check filesystem loading
    print(f"\n=== Filesystem Check ===")
    service = ServiceLocator.get_unified_result_service()
    try:
        results = service.load_analysis_results('task_ed6195726566')
        if results:
            print(f"Results loaded: True")
            print(f"Model slug: {results.model_slug}")
            print(f"App number: {results.app_number}")
            print(f"Status: {results.status}")
            print(f"Total findings: {results.summary.get('total_findings', 0)}")
            print(f"Services count: {len(results.tools)}")
            print(f"Services: {list(results.tools.keys())}")
        else:
            print("Results loaded: False - no results returned")
    except Exception as e:
        print(f"Error loading results: {e}")
        import traceback
        traceback.print_exc()
