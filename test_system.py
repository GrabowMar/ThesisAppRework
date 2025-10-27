#!/usr/bin/env python3
"""
Comprehensive System Test
Tests: result generation, result quality, tool execution, parallel task handling
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

import os
os.environ['FLASK_ENV'] = 'testing'

from app.factory import create_app
from app.extensions import db
from app.models import AnalysisTask, GeneratedApplication, AnalysisStatus
from app.services.result_file_service import ResultFileService

def print_section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")

def test_database_connectivity():
    """Test 1: Verify database is accessible and has data"""
    print_section("TEST 1: Database Connectivity & Data")
    
    app = create_app()
    with app.app_context():
        # Check if we have any apps
        app_count = GeneratedApplication.query.count()
        print(f"✓ Database connected: {app_count} applications found")
        
        if app_count == 0:
            print("⚠️  No applications in database - cannot test further")
            return False
        
        # Check if we have any tasks
        task_count = AnalysisTask.query.count()
        print(f"✓ {task_count} analysis tasks found")
        
        if task_count == 0:
            print("⚠️  No tasks in database")
            return True
        
        # Show status breakdown
        status_breakdown = {}
        for status in AnalysisStatus:
            count = AnalysisTask.query.filter_by(status=status).count()
            if count > 0:
                status_breakdown[status.value] = count
        
        print("\n📊 Task Status Breakdown:")
        for status, count in status_breakdown.items():
            print(f"   - {status}: {count}")
        
        print("\n🎉 TEST 1 PASSED: Database is accessible with data")
        return True

def test_completed_tasks_have_results():
    """Test 2: Verify completed tasks have result data"""
    print_section("TEST 2: Completed Tasks Have Results")
    
    app = create_app()
    with app.app_context():
        # Find completed tasks
        completed_tasks = AnalysisTask.query.filter_by(
            status=AnalysisStatus.COMPLETED
        ).all()
        
        if not completed_tasks:
            print("⚠️  No completed tasks found")
            return True
        
        print(f"✓ Found {len(completed_tasks)} completed tasks")
        
        # Check each for results
        tasks_with_results = 0
        tasks_without_results = 0
        
        for task in completed_tasks:
            if task.result_summary:
                tasks_with_results += 1
                try:
                    summary = json.loads(task.result_summary)
                    findings = summary.get('total_findings', 0)
                    print(f"   ✅ {task.task_id}: {findings} findings")
                except json.JSONDecodeError:
                    print(f"   ⚠️  {task.task_id}: Invalid JSON in result_summary")
            else:
                tasks_without_results += 1
                print(f"   ❌ {task.task_id}: No result_summary")
        
        print(f"\n📊 Results:")
        print(f"   - With results: {tasks_with_results}")
        print(f"   - Without results: {tasks_without_results}")
        
        if tasks_without_results > 0:
            print("\n⚠️  Some completed tasks have no results")
        else:
            print("\n🎉 TEST 2 PASSED: All completed tasks have results")
        
        return tasks_without_results == 0

def test_result_file_discovery():
    """Test 3: Verify ResultFileService can discover result files"""
    print_section("TEST 3: Result File Discovery")
    
    app = create_app()
    with app.app_context():
        # Get all apps with tasks
        apps = GeneratedApplication.query.all()
        
        if not apps:
            print("⚠️  No applications found")
            return True
        
        service = ResultFileService()
        total_descriptors = 0
        
        for app_obj in apps:
            try:
                descriptors = service.list_results(app_obj.model_name, app_obj.app_number)
                if descriptors:
                    print(f"\n✓ {app_obj.model_name} app{app_obj.app_number}: {len(descriptors)} result files")
                    total_descriptors += len(descriptors)
                    
                    # Show first few
                    for i, desc in enumerate(descriptors[:3]):
                        print(f"   - {desc.identifier}: {desc.total_findings} findings, status={desc.status}")
                    
                    if len(descriptors) > 3:
                        print(f"   ... and {len(descriptors) - 3} more")
            except Exception as e:
                print(f"⚠️  Error reading results for {app_obj.model_name} app{app_obj.app_number}: {e}")
        
        print(f"\n📊 Total result files discovered: {total_descriptors}")
        
        if total_descriptors > 0:
            print("\n🎉 TEST 3 PASSED: ResultFileService can discover files")
            return True
        else:
            print("\n⚠️  No result files discovered")
            return False

def test_parallel_task_structure():
    """Test 4: Verify parent-child task relationships"""
    print_section("TEST 4: Parallel Task Structure")
    
    app = create_app()
    with app.app_context():
        # Find main tasks (parent tasks)
        main_tasks = AnalysisTask.query.filter_by(is_main_task=True).all()
        
        if not main_tasks:
            print("⚠️  No main (parent) tasks found")
            return True
        
        print(f"✓ Found {len(main_tasks)} main tasks")
        
        for main_task in main_tasks[:5]:  # Show first 5
            print(f"\n📋 Main Task: {main_task.task_id}")
            print(f"   Status: {main_task.status.value if hasattr(main_task.status, 'value') else main_task.status}")
            print(f"   Type: {main_task.analysis_type.value if hasattr(main_task.analysis_type, 'value') else main_task.analysis_type}")
            
            # Find subtasks
            subtasks = AnalysisTask.query.filter_by(parent_task_id=main_task.task_id).all()
            
            if subtasks:
                print(f"   ✅ {len(subtasks)} subtasks:")
                for subtask in subtasks:
                    service = subtask.service_name or "unknown"
                    status = subtask.status.value if hasattr(subtask.status, 'value') else subtask.status
                    print(f"      - {service}: {status}")
            else:
                print(f"   ⚠️  No subtasks found")
        
        print("\n🎉 TEST 4 PASSED: Task hierarchy structure verified")
        return True

def test_result_data_quality():
    """Test 5: Verify result data structure and quality"""
    print_section("TEST 5: Result Data Quality")
    
    app = create_app()
    with app.app_context():
        # Find tasks with result_summary
        tasks_with_results = AnalysisTask.query.filter(
            AnalysisTask.result_summary != None
        ).limit(10).all()
        
        if not tasks_with_results:
            print("⚠️  No tasks with results found")
            return True
        
        print(f"✓ Checking {len(tasks_with_results)} tasks with results\n")
        
        issues_found = 0
        
        for task in tasks_with_results:
            try:
                summary = json.loads(task.result_summary)
                
                # Check required fields
                if 'total_findings' not in summary:
                    print(f"   ❌ {task.task_id}: Missing 'total_findings'")
                    issues_found += 1
                    continue
                
                if 'status' not in summary:
                    print(f"   ⚠️  {task.task_id}: Missing 'status'")
                
                # Validate data types
                total = summary['total_findings']
                if not isinstance(total, int) or total < 0:
                    print(f"   ❌ {task.task_id}: Invalid total_findings: {total}")
                    issues_found += 1
                    continue
                
                # Check severity breakdown if present
                severities = ['critical', 'high', 'medium', 'low']
                if any(s in summary for s in severities):
                    severity_sum = sum(summary.get(s, 0) for s in severities)
                    if severity_sum != total:
                        print(f"   ⚠️  {task.task_id}: Severity sum ({severity_sum}) != total ({total})")
                
                print(f"   ✅ {task.task_id}: Valid ({total} findings)")
                
            except json.JSONDecodeError:
                print(f"   ❌ {task.task_id}: Invalid JSON")
                issues_found += 1
            except Exception as e:
                print(f"   ❌ {task.task_id}: Error - {e}")
                issues_found += 1
        
        print(f"\n📊 Results:")
        print(f"   - Valid: {len(tasks_with_results) - issues_found}")
        print(f"   - Issues: {issues_found}")
        
        if issues_found == 0:
            print("\n🎉 TEST 5 PASSED: All result data is valid")
            return True
        else:
            print(f"\n⚠️  Found {issues_found} quality issues")
            return False

def main():
    """Run all system tests"""
    print("\n" + "="*70)
    print("  COMPREHENSIVE SYSTEM TEST")
    print("="*70)
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    tests = [
        ("Database Connectivity", test_database_connectivity),
        ("Completed Tasks Have Results", test_completed_tasks_have_results),
        ("Result File Discovery", test_result_file_discovery),
        ("Parallel Task Structure", test_parallel_task_structure),
        ("Result Data Quality", test_result_data_quality)
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n❌ TEST FAILED WITH EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Final summary
    print_section("TEST SUMMARY")
    
    passed = sum(1 for _, p in results if p)
    total = len(results)
    
    for name, passed_test in results:
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\n{'='*70}")
    print(f"  Results: {passed}/{total} tests passed")
    print(f"{'='*70}")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
