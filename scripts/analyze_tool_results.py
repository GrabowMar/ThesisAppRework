"""
Tool Execution Analysis
Analyzes result files to verify all tools executed successfully
"""
import json
import sqlite3
from pathlib import Path
from collections import defaultdict

project_root = Path(__file__).parent.parent
DB_PATH = project_root / 'src' / 'data' / 'thesis_app.db'
RESULTS_DIR = project_root / 'results'

def analyze_all_results():
    """Analyze all result files to check tool execution"""
    print("\n" + "="*80)
    print("  COMPREHENSIVE TOOL EXECUTION ANALYSIS")
    print("="*80 + "\n")
    
    # Get all completed tasks from database
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    
    completed_tasks = cur.execute("""
        SELECT task_id, target_model, target_app_number, status, created_at
        FROM analysis_tasks
        WHERE is_main_task=1 AND status='COMPLETED'
        ORDER BY created_at DESC
        LIMIT 5
    """).fetchall()
    
    conn.close()
    
    print(f"Analyzing {len(completed_tasks)} completed tasks...\n")
    
    # Track tool statistics across all tasks
    all_tools_stats = defaultdict(lambda: {'success': 0, 'failed': 0, 'total': 0})
    service_stats = defaultdict(lambda: {'tasks': 0, 'tools_ok': 0, 'tools_failed': 0})
    
    for task_id, model, app_num, status, created_at in completed_tasks:
        print("="*80)
        print(f"Task: {task_id[:24]}...")
        print(f"Model: {model}, App: {app_num}")
        print(f"Created: {created_at}")
        print("="*80)
        
        # Find result file
        model_clean = model.replace('/', '_')
        app_dir = RESULTS_DIR / model_clean / f'app{app_num}'
        
        if not app_dir.exists():
            print(f"❌ Results directory not found: {app_dir}\n")
            continue
        
        # Find task result file
        task_dirs = list(app_dir.glob(f'**/task*{task_id[:12]}*'))
        
        if not task_dirs:
            print(f"❌ No result directory found for task\n")
            continue
        
        task_dir = task_dirs[0]
        result_files = [f for f in task_dir.glob('*.json') if 'manifest' not in f.name]
        
        if not result_files:
            print(f"❌ No result JSON found\n")
            continue
        
        result_file = result_files[0]
        
        try:
            with open(result_file) as f:
                results = json.load(f)
        except Exception as e:
            print(f"❌ Error reading result file: {e}\n")
            continue
        
        # Analyze results - handle nested structure
        # Try top-level first, then check in 'results' key
        if 'results' in results and isinstance(results['results'], dict):
            result_data = results['results']
            summary = result_data.get('summary', results.get('summary', {}))
            tools = result_data.get('tool_results', results.get('tools', {}))
            services = result_data.get('services', results.get('services', {}))
            findings = result_data.get('findings', results.get('findings', []))
            metadata = results.get('metadata', {})
        else:
            summary = results.get('summary', {})
            tools = results.get('tools', {})
            services = results.get('services', {})
            findings = results.get('findings', [])
            metadata = results.get('metadata', {})
        
        print(f"\n📊 Summary:")
        print(f"   Total Findings: {summary.get('total_findings', 0)}")
        print(f"   Services: {summary.get('services_executed', 0)}")
        print(f"   Tools Executed: {summary.get('tools_executed', 0)}")
        print(f"   Unified Analysis: {metadata.get('unified_analysis', False)}")
        
        # Analyze each service
        print(f"\n📦 Services ({len(services)} total):")
        for service_name, service_data in sorted(services.items()):
            service_stats[service_name]['tasks'] += 1
            
            service_tools = service_data.get('tool_results', {})
            service_summary = service_data.get('summary', {})
            
            tools_ok = 0
            tools_failed = 0
            
            for tool_name, tool_data in service_tools.items():
                if isinstance(tool_data, dict):
                    status = tool_data.get('status', 'unknown')
                    if status in ('success', 'completed'):
                        tools_ok += 1
                    else:
                        tools_failed += 1
            
            service_stats[service_name]['tools_ok'] += tools_ok
            service_stats[service_name]['tools_failed'] += tools_failed
            
            status_icon = "✅" if tools_failed == 0 else "⚠️"
            print(f"   {status_icon} {service_name:22s}: {len(service_tools):2d} tools "
                  f"({tools_ok} ok, {tools_failed} failed)")
        
        # Analyze individual tools
        print(f"\n🔧 Tool Results ({len(tools)} total):")
        
        tools_by_status = {'success': [], 'failed': [], 'error': [], 'unknown': []}
        
        for tool_name, tool_data in sorted(tools.items()):
            if not isinstance(tool_data, dict):
                continue
            
            status = tool_data.get('status', 'unknown').lower()
            executed = tool_data.get('executed', False)
            
            # Normalize status
            if status in ('success', 'completed', 'ok'):
                normalized_status = 'success'
            elif status in ('failed', 'failure'):
                normalized_status = 'failed'
            elif status in ('error', 'exception'):
                normalized_status = 'error'
            else:
                normalized_status = 'unknown'
            
            # Track stats
            all_tools_stats[tool_name]['total'] += 1
            if normalized_status == 'success' and executed:
                all_tools_stats[tool_name]['success'] += 1
                tools_by_status['success'].append(tool_name)
            else:
                all_tools_stats[tool_name]['failed'] += 1
                tools_by_status[normalized_status].append(tool_name)
        
        # Print tool results
        for tool_name in tools_by_status['success']:
            tool_data = tools[tool_name]
            issues = tool_data.get('total_issues', tool_data.get('issue_count', 0))
            duration = tool_data.get('duration_seconds', 0)
            print(f"   ✅ {tool_name:30s} - {issues:3d} issues, {duration:6.2f}s")
        
        for status_type in ['failed', 'error', 'unknown']:
            for tool_name in tools_by_status[status_type]:
                tool_data = tools[tool_name]
                error = tool_data.get('error', 'N/A')[:40]
                print(f"   ❌ {tool_name:30s} - {status_type}: {error}")
        
        # Check for findings
        if findings:
            print(f"\n🔍 Findings ({len(findings)} total):")
            severity_counts = defaultdict(int)
            for finding in findings:
                severity = finding.get('severity', 'unknown')
                severity_counts[severity] += 1
            
            for severity, count in sorted(severity_counts.items()):
                print(f"   {severity}: {count}")
        else:
            print(f"\n🔍 Findings: None")
        
        print("\n")
    
    # Print overall statistics
    print("="*80)
    print("  OVERALL TOOL STATISTICS")
    print("="*80 + "\n")
    
    print("Tool Success Rates:")
    print(f"{'Tool Name':<35s} {'Success':<8s} {'Failed':<8s} {'Total':<8s} {'Rate':<8s}")
    print("-"*80)
    
    for tool_name in sorted(all_tools_stats.keys()):
        stats = all_tools_stats[tool_name]
        total = stats['total']
        success = stats['success']
        failed = stats['failed']
        rate = (success / total * 100) if total > 0 else 0
        
        status_icon = "✅" if rate >= 80 else ("⚠️" if rate >= 50 else "❌")
        print(f"{status_icon} {tool_name:<32s} {success:<8d} {failed:<8d} {total:<8d} {rate:6.1f}%")
    
    print("\n" + "="*80)
    print("  SERVICE STATISTICS")
    print("="*80 + "\n")
    
    print(f"{'Service':<25s} {'Tasks':<8s} {'Tools OK':<12s} {'Tools Failed':<12s} {'Rate':<8s}")
    print("-"*80)
    
    for service_name in sorted(service_stats.keys()):
        stats = service_stats[service_name]
        total_tools = stats['tools_ok'] + stats['tools_failed']
        rate = (stats['tools_ok'] / total_tools * 100) if total_tools > 0 else 0
        
        status_icon = "✅" if rate >= 80 else ("⚠️" if rate >= 50 else "❌")
        print(f"{status_icon} {service_name:<22s} {stats['tasks']:<8d} "
              f"{stats['tools_ok']:<12d} {stats['tools_failed']:<12d} {rate:6.1f}%")
    
    # Final verdict
    print("\n" + "="*80)
    print("  VERDICT")
    print("="*80 + "\n")
    
    total_success = sum(s['success'] for s in all_tools_stats.values())
    total_failed = sum(s['failed'] for s in all_tools_stats.values())
    total_all = total_success + total_failed
    overall_rate = (total_success / total_all * 100) if total_all > 0 else 0
    
    print(f"Overall Tool Success Rate: {overall_rate:.1f}% ({total_success}/{total_all})")
    
    if overall_rate >= 90:
        print("✅ EXCELLENT: Almost all tools are working correctly!")
    elif overall_rate >= 75:
        print("✅ GOOD: Most tools are working, but some need attention")
    elif overall_rate >= 50:
        print("⚠️  WARNING: Significant number of tools are failing")
    else:
        print("❌ CRITICAL: Most tools are not working properly")
    
    # Identify problematic tools
    failing_tools = [name for name, stats in all_tools_stats.items() 
                    if stats['failed'] > stats['success']]
    
    if failing_tools:
        print(f"\n⚠️  Tools with >50% failure rate: {len(failing_tools)}")
        for tool_name in sorted(failing_tools):
            stats = all_tools_stats[tool_name]
            print(f"   - {tool_name}: {stats['failed']}/{stats['total']} failed")

if __name__ == '__main__':
    analyze_all_results()
