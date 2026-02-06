#!/usr/bin/env python3
"""
Re-run Static Analysis for Incomplete Tasks
============================================

This script re-runs static analysis for tasks that had incomplete tool coverage
due to race conditions or tools not running during original analysis.

MUST BE RUN INSIDE THE STATIC-ANALYZER CONTAINER:
    docker compose exec static-analyzer python3 /scripts/rerun_incomplete_static.py

Features:
- Automatically finds existing task directories for each model/app
- Updates results in-place (backs up old results)
- Sequential processing to avoid race conditions
- Comprehensive progress reporting
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, List

# Apps missing static analysis results (model_slug, app_number)
# Total: 83 apps need re-running
MISSING_STATIC_RUNS = [
    # anthropic_claude-4.5-haiku-20251001 (6 apps)
    ("anthropic_claude-4.5-haiku-20251001", 1),
    ("anthropic_claude-4.5-haiku-20251001", 2),
    ("anthropic_claude-4.5-haiku-20251001", 3),
    ("anthropic_claude-4.5-haiku-20251001", 5),
    ("anthropic_claude-4.5-haiku-20251001", 7),
    ("anthropic_claude-4.5-haiku-20251001", 8),
    
    # anthropic_claude-4.5-sonnet-20250929 (9 apps)
    ("anthropic_claude-4.5-sonnet-20250929", 1),
    ("anthropic_claude-4.5-sonnet-20250929", 2),
    ("anthropic_claude-4.5-sonnet-20250929", 3),
    ("anthropic_claude-4.5-sonnet-20250929", 4),
    ("anthropic_claude-4.5-sonnet-20250929", 5),
    ("anthropic_claude-4.5-sonnet-20250929", 6),
    ("anthropic_claude-4.5-sonnet-20250929", 7),
    ("anthropic_claude-4.5-sonnet-20250929", 8),
    ("anthropic_claude-4.5-sonnet-20250929", 10),
    
    # deepseek_deepseek-r1-0528 (9 apps)
    ("deepseek_deepseek-r1-0528", 2),
    ("deepseek_deepseek-r1-0528", 3),
    ("deepseek_deepseek-r1-0528", 4),
    ("deepseek_deepseek-r1-0528", 5),
    ("deepseek_deepseek-r1-0528", 6),
    ("deepseek_deepseek-r1-0528", 7),
    ("deepseek_deepseek-r1-0528", 8),
    ("deepseek_deepseek-r1-0528", 9),
    ("deepseek_deepseek-r1-0528", 10),
    
    # google_gemini-3-flash-preview-20251217 (8 apps)
    ("google_gemini-3-flash-preview-20251217", 2),
    ("google_gemini-3-flash-preview-20251217", 3),
    ("google_gemini-3-flash-preview-20251217", 5),
    ("google_gemini-3-flash-preview-20251217", 6),
    ("google_gemini-3-flash-preview-20251217", 7),
    ("google_gemini-3-flash-preview-20251217", 8),
    ("google_gemini-3-flash-preview-20251217", 9),
    ("google_gemini-3-flash-preview-20251217", 10),
    
    # google_gemini-3-pro-preview-20251117 (7 apps)
    ("google_gemini-3-pro-preview-20251117", 2),
    ("google_gemini-3-pro-preview-20251117", 3),
    ("google_gemini-3-pro-preview-20251117", 4),
    ("google_gemini-3-pro-preview-20251117", 5),
    ("google_gemini-3-pro-preview-20251117", 6),
    ("google_gemini-3-pro-preview-20251117", 8),
    ("google_gemini-3-pro-preview-20251117", 9),
    
    # meta-llama_llama-3.1-405b-instruct (9 apps)
    ("meta-llama_llama-3.1-405b-instruct", 2),
    ("meta-llama_llama-3.1-405b-instruct", 3),
    ("meta-llama_llama-3.1-405b-instruct", 4),
    ("meta-llama_llama-3.1-405b-instruct", 5),
    ("meta-llama_llama-3.1-405b-instruct", 6),
    ("meta-llama_llama-3.1-405b-instruct", 7),
    ("meta-llama_llama-3.1-405b-instruct", 8),
    ("meta-llama_llama-3.1-405b-instruct", 9),
    ("meta-llama_llama-3.1-405b-instruct", 10),
    
    # mistralai_mistral-small-3.1-24b-instruct-2503 (3 apps)
    ("mistralai_mistral-small-3.1-24b-instruct-2503", 3),
    ("mistralai_mistral-small-3.1-24b-instruct-2503", 5),
    ("mistralai_mistral-small-3.1-24b-instruct-2503", 7),
    
    # openai_gpt-4o-mini (4 apps)
    ("openai_gpt-4o-mini", 2),
    ("openai_gpt-4o-mini", 6),
    ("openai_gpt-4o-mini", 7),
    ("openai_gpt-4o-mini", 9),
    
    # openai_gpt-5.2-codex-20260114 (10 apps)
    ("openai_gpt-5.2-codex-20260114", 1),
    ("openai_gpt-5.2-codex-20260114", 2),
    ("openai_gpt-5.2-codex-20260114", 3),
    ("openai_gpt-5.2-codex-20260114", 4),
    ("openai_gpt-5.2-codex-20260114", 5),
    ("openai_gpt-5.2-codex-20260114", 6),
    ("openai_gpt-5.2-codex-20260114", 7),
    ("openai_gpt-5.2-codex-20260114", 8),
    ("openai_gpt-5.2-codex-20260114", 9),
    ("openai_gpt-5.2-codex-20260114", 10),
    
    # qwen_qwen3-coder-plus (10 apps)
    ("qwen_qwen3-coder-plus", 1),
    ("qwen_qwen3-coder-plus", 2),
    ("qwen_qwen3-coder-plus", 3),
    ("qwen_qwen3-coder-plus", 4),
    ("qwen_qwen3-coder-plus", 5),
    ("qwen_qwen3-coder-plus", 6),
    ("qwen_qwen3-coder-plus", 7),
    ("qwen_qwen3-coder-plus", 8),
    ("qwen_qwen3-coder-plus", 9),
    ("qwen_qwen3-coder-plus", 10),
    
    # z-ai_glm-4.7-20251222 (8 apps)
    ("z-ai_glm-4.7-20251222", 1),
    ("z-ai_glm-4.7-20251222", 3),
    ("z-ai_glm-4.7-20251222", 4),
    ("z-ai_glm-4.7-20251222", 5),
    ("z-ai_glm-4.7-20251222", 6),
    ("z-ai_glm-4.7-20251222", 7),
    ("z-ai_glm-4.7-20251222", 9),
    ("z-ai_glm-4.7-20251222", 10),
]


def find_existing_task_dir(results_base: Path, model_slug: str, app_number: int) -> Optional[Path]:
    """Find the existing task directory for a model/app combination.
    
    Prefers non-retry tasks, but will use retry tasks if that's all we have.
    Returns the task directory with services/ subdirectory.
    """
    app_dir = results_base / model_slug / f"app{app_number}"
    if not app_dir.exists():
        return None
    
    # Find all task directories
    task_dirs = [d for d in app_dir.iterdir() if d.is_dir() and d.name.startswith("task")]
    if not task_dirs:
        return None
    
    # Prefer non-retry tasks
    non_retry = [d for d in task_dirs if "retry" not in d.name and "fresh" not in d.name]
    if non_retry:
        # Return first non-retry task
        return sorted(non_retry)[0]
    
    # Fall back to any task
    return sorted(task_dirs)[0]


async def run_static_analysis(
    analyzer, 
    model_slug: str, 
    app_number: int, 
    results_base: Path,
    index: int,
    total: int
) -> Tuple[bool, str]:
    """Run static analysis for a single app and update existing task results."""
    print(f"\n{'='*70}")
    print(f"[{index}/{total}] Re-running: {model_slug} app{app_number}")
    print(f"{'='*70}")
    
    # Find existing task directory
    task_dir = find_existing_task_dir(results_base, model_slug, app_number)
    
    if not task_dir:
        msg = f"No existing task directory found for {model_slug}/app{app_number}"
        print(f"⚠️ {msg}")
        return False, msg
    
    print(f"   Task dir: {task_dir.name}")
    
    # Ensure services directory exists
    services_dir = task_dir / "services"
    services_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Run static analysis using the StaticAnalyzer class
        start_time = datetime.now()
        result = await analyzer.analyze_model_code(model_slug, app_number)
        duration = (datetime.now() - start_time).total_seconds()
        
        tools_used = result.get('tools_used', [])
        print(f"✅ Ran {len(tools_used)} tools in {duration:.1f}s")
        print(f"   Tools: {', '.join(tools_used)}")
        
        # Check tool coverage
        py_results = result.get('results', {}).get('python', {})
        js_results = result.get('results', {}).get('javascript', {})
        py_count = len([k for k in py_results.keys() if k != '_metadata'])
        js_count = len([k for k in js_results.keys() if k != '_metadata'])
        print(f"   Coverage: Python {py_count}/10, JS {js_count}/2")
        
        # Write to static.json (the standard location)
        static_file = services_dir / "static.json"
        
        # Backup old file if exists
        if static_file.exists():
            backup_file = services_dir / f"static.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            static_file.rename(backup_file)
            print(f"   Backed up old: {backup_file.name}")
        
        # Create the result structure
        output = {
            "type": "static_analysis_result",
            "status": "success",
            "service": "static-analyzer",
            "analysis": result,
            "timestamp": datetime.now().isoformat(),
            "rerun": True,
            "rerun_timestamp": datetime.now().isoformat()
        }
        
        # Write new result
        with open(static_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"   ✅ Updated: {static_file.name}")
        
        return True, f"Success: {py_count}/10 Py, {js_count}/2 JS tools"
            
    except Exception as e:
        msg = f"ERROR: {e}"
        print(f"❌ {msg}")
        import traceback
        traceback.print_exc()
        return False, msg


async def main():
    """Re-run static analysis for all apps missing results."""
    # Import the StaticAnalyzer class
    sys.path.insert(0, '/app')
    from main import StaticAnalyzer
    
    # Determine results base path (mounted volume)
    results_base = Path('/app/results')
    if not results_base.exists():
        results_base = Path('/results')
    if not results_base.exists():
        print("ERROR: Cannot find results directory. Expected /app/results or /results")
        return False
    
    total = len(MISSING_STATIC_RUNS)
    print("="*70)
    print("RE-RUNNING STATIC ANALYSIS FOR MISSING RESULTS")
    print("="*70)
    print(f"Results base: {results_base}")
    print(f"Total apps to process: {total}")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    # Initialize the analyzer once
    analyzer = StaticAnalyzer()
    
    results: List[Tuple[str, str, int, bool, str]] = []
    success_count = 0
    fail_count = 0
    
    start_time = datetime.now()
    
    for idx, (model_slug, app_number) in enumerate(MISSING_STATIC_RUNS, 1):
        try:
            success, msg = await run_static_analysis(
                analyzer, model_slug, app_number, results_base, idx, total
            )
            results.append((model_slug, f"app{app_number}", app_number, success, msg))
            if success:
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            msg = f"Exception: {e}"
            print(f"❌ {msg}")
            results.append((model_slug, f"app{app_number}", app_number, False, msg))
            fail_count += 1
        
        # Progress estimate
        elapsed = (datetime.now() - start_time).total_seconds()
        avg_per_app = elapsed / idx
        remaining = (total - idx) * avg_per_app
        print(f"   Progress: {idx}/{total} ({100*idx/total:.1f}%) - ETA: {remaining/60:.1f} min remaining")
    
    # Final summary
    total_time = (datetime.now() - start_time).total_seconds()
    
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"✅ Successful: {success_count}/{total}")
    print(f"❌ Failed: {fail_count}/{total}")
    print(f"⏱️ Total time: {total_time/60:.1f} minutes ({total_time/3600:.2f} hours)")
    print(f"📊 Average: {total_time/total:.1f} seconds per app")
    
    if fail_count > 0:
        print("\n❌ FAILED APPS:")
        for model, app, app_num, success, msg in results:
            if not success:
                print(f"   {model}/{app}: {msg}")
    
    # Save summary to file
    summary_file = results_base / "static_rerun_summary.json"
    summary = {
        "completed_at": datetime.now().isoformat(),
        "total_time_seconds": total_time,
        "total_apps": total,
        "successful": success_count,
        "failed": fail_count,
        "results": [
            {"model": m, "app": a, "success": s, "message": msg}
            for m, a, _, s, msg in results
        ]
    }
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"\n📄 Summary saved to: {summary_file}")
    
    return fail_count == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
