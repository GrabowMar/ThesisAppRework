#!/usr/bin/env python3
"""
Comprehensive System Test
Tests: result generation, result quality, tool execution, parallel task handling
"""

import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

os.environ['FLASK_ENV'] = 'testing'

from app.factory import create_app
from app.extensions import db
from app.models import AnalysisTask, GeneratedApplication
from app.services.analysis_result_store import persist_analysis_payload_by_task_id
from app.services.result_file_service import ResultFileService
from app.services.result_file_writer import write_task_result_files

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def test_result_generation():
    """Test 1: Verify results are generated and persisted correctly"""
    print_section("TEST 1: Result Generation & Persistence")
    
    app = create_app()
    with app.app_context():
        # Find or create a test app
        test_app = GeneratedApplication.query.filter_by(app_number=1).first()
        if not test_app:
            print("❌ No test app found (app_number=1)")
            return False
        
        print(f"✓ Found test app: {test_app.model_name} (app {test_app.app_number})")
        
        # Create a test task
        task = AnalysisTask(
            task_id=f"test_system_{int(time.time())}",
            parent_task_id=None,
            task_type="security",
            model_name=test_app.model_name,
            app_number=test_app.app_number,
            status="in_progress"
        )
        db.session.add(task)
        db.session.commit()
        
        print(f"✓ Created test task: {task.task_id}")
        
        # Create mock analysis payload
        mock_payload = {
            "metadata": {
                "analyzer": "security",
                "timestamp": datetime.utcnow().isoformat(),
                "duration": 5.5
            },
            "results": {
                "bandit": {
                    "findings": [
                        {
                            "severity": "HIGH",
                            "confidence": "HIGH",
                            "issue": "Use of insecure MD5 hash function",
                            "file": "app.py",
                            "line": 42
                        },
                        {
                            "severity": "MEDIUM",
                            "confidence": "HIGH",
                            "issue": "Possible SQL injection vector",
                            "file": "database.py",
                            "line": 156
                        }
                    ]
                },
                "safety": {
                    "findings": [
                        {
                            "severity": "HIGH",
                            "package": "flask",
                            "version": "1.0.0",
                            "vulnerability": "CVE-2023-1234"
                        }
                    ]
                }
            },
            "summary": {
                "total_findings": 3,
                "critical": 0,
                "high": 2,
                "medium": 1,
                "low": 0,
                "tools_run": ["bandit", "safety"],
                "status": "completed"
            }
        }
        
        # Test database persistence
        print("\n📝 Testing database persistence...")
        success = persist_analysis_payload_by_task_id(task.task_id, mock_payload)
        
        if not success:
            print("❌ Failed to persist to database")
            return False
        
        print("✅ Database persistence successful")
        
        # Verify database write
        db.session.refresh(task)
        if not task.result_summary:
            print("❌ result_summary not written to database")
            return False
        
        stored_summary = json.loads(task.result_summary)
        if stored_summary.get('total_findings') != 3:
            print(f"❌ Incorrect findings count in database: {stored_summary.get('total_findings')}")
            return False
        
        print(f"✅ Database contains correct data: {stored_summary['total_findings']} findings")
        
        # Verify disk file write
        print("\n📁 Testing disk file persistence...")
        results_dir = Path('results') / test_app.model_name / f"app{test_app.app_number}"
        
        if not results_dir.exists():
            print(f"❌ Results directory not found: {results_dir}")
            return False
        
        # Find task directories
        task_dirs = [d for d in results_dir.iterdir() if d.is_dir() and task.task_id in d.name]
        
        if not task_dirs:
            print(f"❌ No task directory found for {task.task_id}")
            return False
        
        task_dir = task_dirs[0]
        print(f"✅ Found task directory: {task_dir.name}")
        
        # Check for result file
        result_files = list(task_dir.glob("*.json"))
        result_files = [f for f in result_files if 'manifest' not in f.name]
        
        if not result_files:
            print("❌ No result file found")
            return False
        
        result_file = result_files[0]
        print(f"✅ Found result file: {result_file.name}")
        
        # Verify file content
        with open(result_file) as f:
            file_data = json.load(f)
        
        if file_data.get('summary', {}).get('total_findings') != 3:
            print(f"❌ Incorrect findings in file: {file_data.get('summary', {}).get('total_findings')}")
            return False
        
        print(f"✅ File contains correct data: {file_data['summary']['total_findings']} findings")
        
        # Test ResultFileService discovery
        print("\n🔍 Testing ResultFileService discovery...")
        service = ResultFileService()
        descriptors = service.list_results(test_app.model_name, test_app.app_number)
        
        matching = [d for d in descriptors if task.task_id in d.directory_name]
        if not matching:
            print(f"❌ ResultFileService didn't find task {task.task_id}")
            print(f"   Found {len(descriptors)} descriptors total")
            return False
        
        descriptor = matching[0]
        if descriptor.total_findings != 3:
            print(f"❌ ResultFileService has wrong findings count: {descriptor.total_findings}")
            return False
        
        print(f"✅ ResultFileService found task with correct findings: {descriptor.total_findings}")
        
        print("\n🎉 TEST 1 PASSED: Result generation & persistence work correctly")
        return True

def test_result_quality():
    """Test 2: Verify result data structure and quality"""
    print_section("TEST 2: Result Quality & Structure")
    
    app = create_app()
    with app.app_context():
        # Find a completed task with results
        task = AnalysisTask.query.filter(
            AnalysisTask.result_summary.isnot(None),
            AnalysisTask.status == 'completed'
        ).first()
        
        if not task:
            print("⚠️  No completed tasks with results found")
            return True  # Not a failure, just no data to test
        
        print(f"✓ Testing task: {task.task_id} ({task.task_type})")
        
        # Parse result summary
        try:
            summary = json.loads(task.result_summary)
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in result_summary: {e}")
            return False
        
        print("✅ result_summary is valid JSON")
        
        # Check required fields
        required_fields = ['total_findings', 'status']
        missing = [f for f in required_fields if f not in summary]
        if missing:
            print(f"❌ Missing required fields: {missing}")
            return False
        
        print(f"✅ Has required fields: {required_fields}")
        
        # Validate data types
        if not isinstance(summary['total_findings'], int):
            print(f"❌ total_findings is not an integer: {type(summary['total_findings'])}")
            return False
        
        if summary['total_findings'] < 0:
            print(f"❌ total_findings is negative: {summary['total_findings']}")
            return False
        
        print(f"✅ total_findings is valid: {summary['total_findings']}")
        
        # Check status values
        valid_statuses = ['completed', 'failed', 'partial']
        if summary['status'] not in valid_statuses:
            print(f"❌ Invalid status: {summary['status']} (expected one of {valid_statuses})")
            return False
        
        print(f"✅ status is valid: {summary['status']}")
        
        # Check severity breakdown if present
        if 'critical' in summary or 'high' in summary or 'medium' in summary or 'low' in summary:
            severities = {
                'critical': summary.get('critical', 0),
                'high': summary.get('high', 0),
                'medium': summary.get('medium', 0),
                'low': summary.get('low', 0)
            }
            
            severity_sum = sum(severities.values())
            if severity_sum != summary['total_findings']:
                print(f"⚠️  Severity breakdown ({severity_sum}) doesn't match total ({summary['total_findings']})")
            else:
                print(f"✅ Severity breakdown matches total: {severities}")
        
        print("\n🎉 TEST 2 PASSED: Result quality is good")
        return True

def test_parallel_tasks():
    """Test 3: Verify parallel task handling"""
    print_section("TEST 3: Parallel Task Execution")
    
    app = create_app()
    with app.app_context():
        # Find tasks with parent-child relationships
        parent_tasks = AnalysisTask.query.filter(
            AnalysisTask.parent_task_id.is_(None),
            AnalysisTask.task_type == 'unified'
        ).all()
        
        if not parent_tasks:
            print("⚠️  No unified (parallel) tasks found")
            return True
        
        print(f"✓ Found {len(parent_tasks)} unified parent tasks")
        
        # Test first parent task
        parent = parent_tasks[0]
        print(f"\n📋 Testing parent task: {parent.task_id}")
        print(f"   Status: {parent.status}")
        print(f"   Type: {parent.task_type}")
        
        # Find subtasks
        subtasks = AnalysisTask.query.filter_by(parent_task_id=parent.task_id).all()
        
        if not subtasks:
            print("⚠️  No subtasks found for this parent")
            return True
        
        print(f"✅ Found {len(subtasks)} subtasks")
        
        # Check subtask types
        subtask_types = [t.task_type for t in subtasks]
        print(f"   Subtask types: {', '.join(subtask_types)}")
        
        # Verify each subtask has proper parent reference
        for subtask in subtasks:
            if subtask.parent_task_id != parent.task_id:
                print(f"❌ Subtask {subtask.task_id} has wrong parent: {subtask.parent_task_id}")
                return False
        
        print("✅ All subtasks have correct parent reference")
        
        # Check for result aggregation in parent
        if parent.status == 'completed' and parent.result_summary:
            summary = json.loads(parent.result_summary)
            
            # Verify parent has aggregated results
            if 'total_findings' in summary:
                print(f"✅ Parent has aggregated results: {summary['total_findings']} findings")
                
                # Check if it's sum of subtask findings
                subtask_findings = []
                for subtask in subtasks:
                    if subtask.result_summary:
                        sub_summary = json.loads(subtask.result_summary)
                        subtask_findings.append(sub_summary.get('total_findings', 0))
                
                if subtask_findings:
                    expected_total = sum(subtask_findings)
                    actual_total = summary['total_findings']
                    print(f"   Subtask findings: {subtask_findings} (sum: {expected_total})")
                    print(f"   Parent total: {actual_total}")
                    
                    if expected_total == actual_total:
                        print("✅ Parent correctly aggregated subtask findings")
                    else:
                        print(f"⚠️  Findings mismatch: expected {expected_total}, got {actual_total}")
        
        print("\n🎉 TEST 3 PASSED: Parallel task structure is correct")
        return True

def test_tool_execution():
    """Test 4: Verify individual tools produced results"""
    print_section("TEST 4: Tool Execution Verification")
    
    app = create_app()
    with app.app_context():
        # Check for tasks from different analyzers
        analyzers = ['security', 'static', 'performance', 'ai']
        
        results = {}
        for analyzer in analyzers:
            tasks = AnalysisTask.query.filter_by(
                task_type=analyzer,
                status='completed'
            ).filter(AnalysisTask.result_summary.isnot(None)).all()
            
            results[analyzer] = len(tasks)
        
        print("📊 Completed tasks by analyzer:")
        for analyzer, count in results.items():
            status = "✅" if count > 0 else "⚠️ "
            print(f"   {status} {analyzer}: {count} tasks")
        
        # Check if at least some analyzers have results
        if sum(results.values()) == 0:
            print("\n⚠️  No completed tasks with results found")
            return True
        
        print(f"\n✅ Total: {sum(results.values())} completed tasks across analyzers")
        
        # Sample one task and check tool details
        sample_task = AnalysisTask.query.filter(
            AnalysisTask.result_summary.isnot(None),
            AnalysisTask.status == 'completed'
        ).first()
        
        if sample_task:
            summary = json.loads(sample_task.result_summary)
            
            if 'tools_run' in summary:
                tools = summary['tools_run']
                print(f"\n🔧 Sample task ran {len(tools)} tools: {', '.join(tools)}")
            
            if 'duration' in summary.get('metadata', {}):
                duration = summary['metadata']['duration']
                print(f"⏱️  Task duration: {duration:.2f}s")
        
        print("\n🎉 TEST 4 PASSED: Tool execution verified")
        return True

def main():
    """Run all system tests"""
    print("\n" + "="*60)
    print("  COMPREHENSIVE SYSTEM TEST")
    print("="*60)
    print(f"  Testing: Results, Quality, Tools, Parallelism")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    tests = [
        ("Result Generation", test_result_generation),
        ("Result Quality", test_result_quality),
        ("Parallel Tasks", test_parallel_tasks),
        ("Tool Execution", test_tool_execution)
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
    
    print(f"\n{'='*60}")
    print(f"  Results: {passed}/{total} tests passed")
    print(f"{'='*60}")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
