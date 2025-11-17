#!/usr/bin/env python
"""
Verification script to check tool output parity between:
1. Filesystem JSON (results/...)
2. Database (AnalysisTask.result_summary)
3. UI display (what templates render)
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app.factory import create_app
from app.models import AnalysisTask
from app.services.unified_result_service import UnifiedResultService

def compare_tools_output(task_id: str):
    """Compare tool outputs across all sources."""
    
    print(f"\n{'='*80}")
    print(f"TOOL OUTPUT VERIFICATION FOR: {task_id}")
    print(f"{'='*80}\n")
    
    app = create_app()
    
    with app.app_context():
        # 1. Get from database
        task = AnalysisTask.query.filter_by(task_id=task_id).first()
        if not task:
            print(f"❌ Task {task_id} not found in database")
            return False
        
        db_summary = task.get_result_summary() if task.result_summary else None
        db_tools = db_summary.get('results', {}).get('tools', {}) if db_summary else {}
        
        # 2. Get from filesystem
        service = UnifiedResultService()
        fs_results = service.load_analysis_results(task_id, force_refresh=True)
        
        # Get the actual tools map from raw data
        fs_tools = fs_results.raw_data.get('results', {}).get('tools', {}) if fs_results else {}
        
        # 3. Compare
        print("TOOL OUTPUTS COMPARISON\n")
        
        tools_list = []
        all_tools = set(db_tools.keys()) | set(fs_tools.keys())
        
        for tool_name in sorted(all_tools):
            db_tool = db_tools.get(tool_name, {})
            fs_tool = fs_tools.get(tool_name, {})
            
            db_status = db_tool.get('status', 'missing')
            db_issues = db_tool.get('total_issues', '-')
            
            fs_status = fs_tool.get('status', 'missing')
            fs_issues = fs_tool.get('total_issues', '-')
            
            match = '✅' if (db_status == fs_status and db_issues == fs_issues) else '❌'
            
            tools_list.append([
                tool_name,
                db_status,
                db_issues if db_issues != 0 else '—',
                fs_status,
                fs_issues if fs_issues != 0 else '—',
                match
            ])
        
        headers = ['Tool', 'DB Status', 'DB Issues', 'FS Status', 'FS Issues', 'Match']
        
        # Print table manually
        col_widths = [15, 12, 10, 12, 10, 6]
        header_line = "  ".join(h.ljust(w) for h, w in zip(headers, col_widths))
        print(header_line)
        print("-" * len(header_line))
        
        for row in tools_list:
            row_line = "  ".join(str(cell).ljust(w) for cell, w in zip(row, col_widths))
            print(row_line)
        
        # 4. Check what UI template would show
        print(f"\n{'='*80}")
        print("UI DISPLAY (what user sees)")
        print(f"{'='*80}\n")
        
        ui_display = []
        for tool_name in sorted(all_tools):
            tool_data = fs_tools.get(tool_name, {})
            status = tool_data.get('status', 'unknown')
            issues = tool_data.get('total_issues', 0)
            
            # Simulate what the UI badge would show
            if status in ['success', 'ok', 'completed', 'no_issues']:
                if issues == 0:
                    display_text = f"{tool_name.capitalize()}\t—\tNo issues found"
                else:
                    display_text = f"{tool_name.capitalize()}\t•\t{issues} issue(s)"
            elif status in ['failed', 'error', 'timeout']:
                display_text = f"{tool_name.capitalize()}\t❌\tFailed ({status})"
            else:
                display_text = f"{tool_name.capitalize()}\t?\t{status}"
            
            ui_display.append(display_text)
        
        for line in ui_display:
            print(line)
        
        # 5. Summary
        print(f"\n{'='*80}")
        print("SUMMARY")
        print(f"{'='*80}\n")
        
        total_tools = len(all_tools)
        tools_with_issues = sum(1 for t in fs_tools.values() if (t.get('total_issues') or 0) > 0)
        tools_clean = sum(1 for t in fs_tools.values() if (t.get('total_issues') or 0) == 0 and t.get('status') in ['success', 'ok', 'no_issues'])
        tools_failed = sum(1 for t in fs_tools.values() if t.get('status') in ['failed', 'error', 'timeout'])
        
        print(f"Total tools executed:     {total_tools}")
        print(f"Tools with findings:      {tools_with_issues}")
        print(f"Clean (no issues):        {tools_clean}")
        print(f"Failed/Error:             {tools_failed}")
        
        # Check specific tools mentioned by user
        print(f"\n{'='*80}")
        print("USER'S SPECIFIC TOOLS")
        print(f"{'='*80}\n")
        
        user_tools = ['bandit', 'pylint', 'semgrep', 'mypy', 'safety', 'pip-audit', 
                      'vulture', 'ruff', 'flake8', 'eslint', 'npm-audit', 'stylelint']
        
        for tool in user_tools:
            tool_data = fs_tools.get(tool, {})
            status = tool_data.get('status', 'NOT FOUND')
            issues = tool_data.get('total_issues', 'N/A')
            
            expected = {
                'bandit': (0, 'No issues'),
                'pylint': (61, '61 issues'),
                'semgrep': (0, 'No issues'),
                'mypy': (0, 'No issues'),
                'safety': (0, 'No issues'),
                'pip-audit': (0, 'No issues'),
                'vulture': (0, 'No issues'),
                'ruff': (0, 'No issues'),
                'flake8': (0, 'No issues'),
                'eslint': (0, 'No issues'),
                'npm-audit': (0, 'No issues'),
                'stylelint': (0, 'No issues')
            }
            
            exp_issues, exp_text = expected.get(tool, (None, 'Unknown'))
            
            if tool in fs_tools:
                actual_text = f"{issues} issue(s)" if issues > 0 else "No issues"
                match_icon = '✅' if issues == exp_issues else '❌'
                print(f"{match_icon} {tool.capitalize():<15} Expected: {exp_text:<15} Actual: {actual_text} (status: {status})")
            else:
                print(f"❓ {tool.capitalize():<15} Expected: {exp_text:<15} Actual: NOT EXECUTED")
        
        return True

if __name__ == '__main__':
    # Use the latest task for claude-4.5-haiku app1
    task_id = 'task_358365b03c2c'
    
    if len(sys.argv) > 1:
        task_id = sys.argv[1]
    
    try:
        compare_tools_output(task_id)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
