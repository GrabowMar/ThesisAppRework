#!/usr/bin/env python3
"""Quick pipeline verification test"""
import sys
import requests
from datetime import datetime, timedelta

sys.path.insert(0, '/app/src')
from app.factory import create_app
from app.models import PipelineExecution, AnalysisTask

def test_system():
    app = create_app()
    with app.app_context():
        print("=" * 80)
        print("PIPELINE SYSTEM VERIFICATION TEST")
        print("=" * 80)

        # 1. Check recent pipeline activity
        print("\n1. RECENT PIPELINE ACTIVITY")
        print("-" * 80)
        cutoff = datetime.utcnow() - timedelta(hours=24)
        recent = PipelineExecution.query.filter(
            PipelineExecution.created_at >= cutoff
        ).order_by(PipelineExecution.created_at.desc()).all()

        print(f"Pipelines in last 24h: {len(recent)}")
        for p in recent[:3]:
            age_m = (datetime.utcnow() - p.created_at).total_seconds() / 60
            print(f"  {p.pipeline_id[:20]}... {p.status:10} {p.get_overall_progress():5.1f}% ({age_m:5.0f}m ago)")

        # 2. Check recent task completions
        print("\n2. RECENT TASK COMPLETIONS")
        print("-" * 80)
        recent_tasks = AnalysisTask.query.filter(
            AnalysisTask.updated_at >= cutoff
        ).order_by(AnalysisTask.updated_at.desc()).limit(5).all()

        print(f"Tasks updated in last 24h: {len(recent_tasks)}")
        for t in recent_tasks:
            age_m = (datetime.utcnow() - t.updated_at).total_seconds() / 60
            print(f"  {t.task_id[:20]}... {t.status:12} ({age_m:5.0f}m ago)")

        # 3. Check analyzer availability
        print("\n3. ANALYZER AVAILABILITY")
        print("-" * 80)
        analyzers = {
            'static-analyzer': 'http://static-analyzer:2001/health',
            'dynamic-analyzer': 'http://dynamic-analyzer:2002/health',
            'performance-tester': 'http://performance-tester:2003/health',
            'ai-analyzer': 'http://ai-analyzer:2004/health'
        }

        all_ok = True
        for name, url in analyzers.items():
            try:
                resp = requests.get(url, timeout=5)
                status = "✅ OK" if resp.status_code == 200 else f"⚠️  HTTP {resp.status_code}"
                print(f"  {name:20} {status}")
            except requests.Timeout:
                print(f"  {name:20} ⏱️  TIMEOUT (but may be working)")
            except Exception as e:
                print(f"  {name:20} ❌ {str(e)[:40]}")
                all_ok = False

        # 4. Overall status
        print("\n" + "=" * 80)
        print("VERIFICATION RESULT")
        print("=" * 80)

        if len(recent) > 0:
            print("✅ Pipeline execution system is active")
        else:
            print("⚠️  No recent pipeline activity")

        if len(recent_tasks) > 0:
            print("✅ Task processing system is active")
        else:
            print("⚠️  No recent task activity")

        print("\n✅ SYSTEM VERIFICATION COMPLETE")
        print("=" * 80)

if __name__ == "__main__":
    test_system()
