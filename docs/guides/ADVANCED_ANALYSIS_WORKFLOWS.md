# Advanced Analysis Workflows

This guide covers advanced use cases, optimization strategies, and complex scenarios for the ThesisAppRework analysis system.

## 📋 Table of Contents

1. [Batch Processing](#batch-processing)
2. [Parallel Analysis](#parallel-analysis)
3. [Custom Tool Selection](#custom-tool-selection)
4. [Result Aggregation](#result-aggregation)
5. [Integration Patterns](#integration-patterns)
6. [Performance Optimization](#performance-optimization)
7. [Error Recovery](#error-recovery)
8. [Advanced Filtering](#advanced-filtering)

---

## 🔄 Batch Processing

### Basic Batch Analysis

Process multiple applications in sequence:

```bash
# Create batch configuration
cat > batch_config.json << EOF
[
  ["openai_gpt-4", 1],
  ["openai_gpt-4", 2],
  ["anthropic_claude-3.7-sonnet", 1],
  ["anthropic_claude-3.7-sonnet", 2]
]
EOF

# Run batch analysis
python analyzer/analyzer_manager.py batch batch_config.json
```

### Quick Multi-Model Batch

Analyze app 1 across multiple models:

```bash
python analyzer/analyzer_manager.py batch-models \
  openai_gpt-4,anthropic_claude-3.7-sonnet,google_gemini-pro
```

### Custom Batch Script

```python
#!/usr/bin/env python3
"""Custom batch analysis with error handling and notifications."""

import asyncio
import json
from pathlib import Path
from analyzer.analyzer_manager import AnalyzerManager

async def batch_with_notifications(models_and_apps, analysis_type='comprehensive'):
    """Run batch analysis with progress notifications."""
    manager = AnalyzerManager()
    results = []
    total = len(models_and_apps)
    
    for idx, (model, app) in enumerate(models_and_apps, 1):
        print(f"\n[{idx}/{total}] Analyzing {model} app{app}...")
        
        try:
            if analysis_type == 'comprehensive':
                result = await manager.run_comprehensive_analysis(model, app)
            elif analysis_type == 'security':
                result = await manager.run_security_analysis(model, app)
            else:
                result = await manager.run_static_analysis(model, app)
            
            results.append({
                'model': model,
                'app': app,
                'status': 'success',
                'findings': result.get('summary', {}).get('total_findings', 0)
            })
            print(f"✅ Success: {result.get('summary', {}).get('total_findings', 0)} findings")
            
        except Exception as e:
            results.append({
                'model': model,
                'app': app,
                'status': 'error',
                'error': str(e)
            })
            print(f"❌ Failed: {e}")
    
    # Save summary
    summary_path = Path('results/batch_summary.json')
    with open(summary_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📊 Batch complete. Summary saved to: {summary_path}")
    return results

# Usage
if __name__ == '__main__':
    models_apps = [
        ('openai_gpt-4', 1),
        ('anthropic_claude-3.7-sonnet', 1),
        ('google_gemini-pro', 1),
    ]
    asyncio.run(batch_with_notifications(models_apps, 'security'))
```

---

## ⚡ Parallel Analysis

### Concurrent Analysis (Multiple Apps)

```python
#!/usr/bin/env python3
"""Parallel analysis with asyncio concurrency control."""

import asyncio
from analyzer.analyzer_manager import AnalyzerManager

async def parallel_analysis(tasks, max_concurrent=3):
    """Run multiple analyses concurrently with rate limiting."""
    manager = AnalyzerManager()
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def analyze_with_limit(model, app, analysis_type):
        async with semaphore:
            print(f"Starting: {model} app{app} ({analysis_type})")
            if analysis_type == 'comprehensive':
                result = await manager.run_comprehensive_analysis(model, app)
            elif analysis_type == 'security':
                result = await manager.run_security_analysis(model, app)
            else:
                result = await manager.run_static_analysis(model, app)
            print(f"Finished: {model} app{app}")
            return result
    
    # Create tasks
    coros = [
        analyze_with_limit(model, app, analysis_type)
        for model, app, analysis_type in tasks
    ]
    
    # Run in parallel
    results = await asyncio.gather(*coros, return_exceptions=True)
    return results

# Usage
if __name__ == '__main__':
    tasks = [
        ('openai_gpt-4', 1, 'static'),
        ('openai_gpt-4', 2, 'static'),
        ('anthropic_claude-3.7-sonnet', 1, 'static'),
        ('anthropic_claude-3.7-sonnet', 2, 'static'),
    ]
    
    results = asyncio.run(parallel_analysis(tasks, max_concurrent=2))
    print(f"Completed {len(results)} analyses")
```

### API-Based Parallel Submission

```bash
#!/bin/bash
# Submit multiple analyses in parallel via API

TOKEN="your_bearer_token_here"
BASE_URL="http://localhost:5000"

# Function to submit analysis
submit_analysis() {
    model=$1
    app=$2
    type=$3
    
    curl -X POST "$BASE_URL/api/analysis/run" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d "{
        \"model_slug\": \"$model\",
        \"app_number\": $app,
        \"analysis_type\": \"$type\"
      }" &
}

# Submit 4 analyses in parallel
submit_analysis "openai_gpt-4" 1 "security"
submit_analysis "openai_gpt-4" 2 "security"
submit_analysis "anthropic_claude-3.7-sonnet" 1 "security"
submit_analysis "anthropic_claude-3.7-sonnet" 2 "security"

# Wait for all to complete
wait

echo "All analyses submitted!"
```

---

## 🎯 Custom Tool Selection

### Focus on Specific Tools

```bash
# Only run Bandit (Python security scanner)
python analyzer/analyzer_manager.py analyze openai_gpt-4 1 security \
  --tools bandit

# Only ESLint (JavaScript linter)
python analyzer/analyzer_manager.py analyze openai_gpt-4 1 static \
  --tools eslint

# Multiple specific tools
python analyzer/analyzer_manager.py analyze openai_gpt-4 1 security \
  --tools bandit,safety,semgrep

# Performance testing with only Apache Bench
python analyzer/analyzer_manager.py analyze openai_gpt-4 1 performance \
  --tools ab
```

### Programmatic Tool Selection

```python
#!/usr/bin/env python3
"""Selective tool execution based on app characteristics."""

import asyncio
from pathlib import Path
from analyzer.analyzer_manager import AnalyzerManager

async def smart_tool_selection(model, app):
    """Choose tools based on app characteristics."""
    manager = AnalyzerManager()
    app_path = Path(f"generated/apps/{model}/app{app}")
    
    # Detect languages
    has_python = list(app_path.rglob("*.py"))
    has_javascript = list(app_path.rglob("*.js"))
    
    # Build tool list
    tools = []
    
    if has_python:
        tools.extend(['bandit', 'safety', 'pylint'])
    
    if has_javascript:
        tools.extend(['eslint', 'jshint'])
    
    print(f"Detected tools needed: {tools}")
    
    # Run targeted analysis
    result = await manager.run_static_analysis(model, app, tools=tools)
    return result

# Usage
if __name__ == '__main__':
    asyncio.run(smart_tool_selection('openai_gpt-4', 1))
```

---

## 📊 Result Aggregation

### Cross-Model Comparison

```python
#!/usr/bin/env python3
"""Compare analysis results across multiple models."""

import json
from pathlib import Path
from collections import defaultdict

def aggregate_results(models, app_number=1):
    """Aggregate results across multiple models for same app."""
    aggregated = defaultdict(lambda: {
        'total_findings': [],
        'critical_findings': [],
        'high_findings': [],
        'tools_successful': [],
        'duration': []
    })
    
    for model in models:
        # Find latest result for this model/app
        result_dir = Path(f"results/{model}/app{app_number}")
        task_dirs = sorted(result_dir.glob("task_*"), key=lambda p: p.stat().st_mtime, reverse=True)
        
        if not task_dirs:
            continue
        
        latest_task = task_dirs[0]
        result_files = list(latest_task.glob("*.json"))
        
        if not result_files:
            continue
        
        with open(result_files[0]) as f:
            data = json.load(f)
        
        summary = data.get('summary', {})
        aggregated[model]['total_findings'] = summary.get('total_findings', 0)
        aggregated[model]['critical_findings'] = summary.get('findings_by_severity', {}).get('critical', 0)
        aggregated[model]['high_findings'] = summary.get('findings_by_severity', {}).get('high', 0)
        aggregated[model]['tools_successful'] = summary.get('tools_successful', 0)
        aggregated[model]['duration'] = data.get('metadata', {}).get('duration_seconds', 0)
    
    return dict(aggregated)

# Usage
if __name__ == '__main__':
    models = ['openai_gpt-4', 'anthropic_claude-3.7-sonnet', 'google_gemini-pro']
    results = aggregate_results(models, app_number=1)
    
    print("\n📊 Cross-Model Comparison (App 1)\n")
    print(f"{'Model':<40} {'Findings':<10} {'Critical':<10} {'High':<10} {'Duration':<10}")
    print("-" * 80)
    
    for model, data in results.items():
        print(f"{model:<40} {data['total_findings']:<10} {data['critical_findings']:<10} {data['high_findings']:<10} {data['duration']:<10.1f}s")
```

### Historical Trend Analysis

```python
#!/usr/bin/env python3
"""Analyze trends in findings over time."""

import json
from pathlib import Path
from datetime import datetime
import matplotlib.pyplot as plt

def analyze_trends(model, app_number):
    """Plot finding trends over time."""
    result_dir = Path(f"results/{model}/app{app_number}")
    task_dirs = sorted(result_dir.glob("task_*"), key=lambda p: p.stat().st_mtime)
    
    timestamps = []
    total_findings = []
    critical_findings = []
    
    for task_dir in task_dirs:
        result_files = list(task_dir.glob("*.json"))
        if not result_files:
            continue
        
        with open(result_files[0]) as f:
            data = json.load(f)
        
        timestamp = datetime.fromisoformat(data['metadata']['timestamp'].replace('Z', '+00:00'))
        timestamps.append(timestamp)
        
        summary = data.get('summary', {})
        total_findings.append(summary.get('total_findings', 0))
        critical_findings.append(summary.get('findings_by_severity', {}).get('critical', 0))
    
    # Plot
    plt.figure(figsize=(12, 6))
    plt.plot(timestamps, total_findings, marker='o', label='Total Findings')
    plt.plot(timestamps, critical_findings, marker='s', label='Critical Findings', color='red')
    plt.xlabel('Date')
    plt.ylabel('Count')
    plt.title(f'Finding Trends: {model} App {app_number}')
    plt.legend()
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(f'results/{model}_app{app_number}_trends.png')
    print(f"Chart saved to: results/{model}_app{app_number}_trends.png")

# Usage
if __name__ == '__main__':
    analyze_trends('openai_gpt-4', 1)
```

---

## 🔌 Integration Patterns

### GitHub Actions Integration

```yaml
# .github/workflows/analyze.yml
name: Code Analysis

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  analyze:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r analyzer/requirements.txt
    
    - name: Start analyzer services
      run: |
        python analyzer/analyzer_manager.py start
        sleep 30  # Wait for services to be ready
    
    - name: Run security analysis
      env:
        OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
      run: |
        python analyzer/analyzer_manager.py analyze openai_gpt-4 1 security --tools bandit,safety
    
    - name: Check for critical findings
      run: |
        python scripts/check_findings.py --fail-on-critical
    
    - name: Upload results
      uses: actions/upload-artifact@v3
      with:
        name: analysis-results
        path: results/
```

### Jenkins Pipeline

```groovy
// Jenkinsfile
pipeline {
    agent any
    
    environment {
        OPENROUTER_API_KEY = credentials('openrouter-api-key')
    }
    
    stages {
        stage('Setup') {
            steps {
                sh 'pip install -r requirements.txt'
                sh 'pip install -r analyzer/requirements.txt'
            }
        }
        
        stage('Start Services') {
            steps {
                sh 'python analyzer/analyzer_manager.py start'
                sleep 30
            }
        }
        
        stage('Security Scan') {
            steps {
                sh 'python analyzer/analyzer_manager.py analyze openai_gpt-4 1 security'
            }
        }
        
        stage('Static Analysis') {
            steps {
                sh 'python analyzer/analyzer_manager.py analyze openai_gpt-4 1 static'
            }
        }
        
        stage('Report') {
            steps {
                archiveArtifacts artifacts: 'results/**/*.json', fingerprint: true
                publishHTML([
                    reportDir: 'results',
                    reportFiles: '*.html',
                    reportName: 'Analysis Report'
                ])
            }
        }
    }
    
    post {
        always {
            sh 'python analyzer/analyzer_manager.py stop'
        }
    }
}
```

### Webhook Integration

```python
#!/usr/bin/env python3
"""Webhook receiver for external analysis triggers."""

from flask import Flask, request, jsonify
import asyncio
from analyzer.analyzer_manager import AnalyzerManager

app = Flask(__name__)

@app.route('/webhook/analyze', methods=['POST'])
def webhook_analyze():
    """Receive webhook and trigger analysis."""
    data = request.json
    
    model = data.get('model')
    app_number = data.get('app_number')
    analysis_type = data.get('analysis_type', 'comprehensive')
    
    if not model or not app_number:
        return jsonify({'error': 'Missing model or app_number'}), 400
    
    # Trigger async analysis
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    manager = AnalyzerManager()
    
    try:
        if analysis_type == 'comprehensive':
            result = loop.run_until_complete(
                manager.run_comprehensive_analysis(model, app_number)
            )
        elif analysis_type == 'security':
            result = loop.run_until_complete(
                manager.run_security_analysis(model, app_number)
            )
        else:
            result = loop.run_until_complete(
                manager.run_static_analysis(model, app_number)
            )
        
        return jsonify({
            'status': 'success',
            'findings': result.get('summary', {}).get('total_findings', 0)
        })
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500
    finally:
        loop.close()

if __name__ == '__main__':
    app.run(port=5001)
```

---

## ⚙️ Performance Optimization

### Resource Management

```python
#!/usr/bin/env python3
"""Optimize resource usage during batch analysis."""

import asyncio
import psutil
from analyzer.analyzer_manager import AnalyzerManager

async def resource_aware_batch(tasks, max_cpu_percent=80, max_memory_percent=80):
    """Run batch with resource monitoring."""
    manager = AnalyzerManager()
    results = []
    
    for model, app in tasks:
        # Check resources before starting
        cpu_percent = psutil.cpu_percent(interval=1)
        memory_percent = psutil.virtual_memory().percent
        
        # Wait if resources are high
        while cpu_percent > max_cpu_percent or memory_percent > max_memory_percent:
            print(f"⏳ Waiting for resources (CPU: {cpu_percent}%, MEM: {memory_percent}%)")
            await asyncio.sleep(30)
            cpu_percent = psutil.cpu_percent(interval=1)
            memory_percent = psutil.virtual_memory().percent
        
        print(f"✅ Resources available (CPU: {cpu_percent}%, MEM: {memory_percent}%)")
        print(f"🔍 Analyzing {model} app{app}")
        
        result = await manager.run_comprehensive_analysis(model, app)
        results.append(result)
    
    return results

# Usage
if __name__ == '__main__':
    tasks = [
        ('openai_gpt-4', 1),
        ('openai_gpt-4', 2),
        ('anthropic_claude-3.7-sonnet', 1),
    ]
    asyncio.run(resource_aware_batch(tasks))
```

### Caching Strategy

```python
#!/usr/bin/env python3
"""Cache static analysis results to avoid redundant scans."""

import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta

def get_code_hash(app_path):
    """Generate hash of all code files."""
    hasher = hashlib.sha256()
    for file_path in sorted(app_path.rglob("*.py")):
        hasher.update(file_path.read_bytes())
    for file_path in sorted(app_path.rglob("*.js")):
        hasher.update(file_path.read_bytes())
    return hasher.hexdigest()

def is_cache_valid(model, app_number, max_age_hours=24):
    """Check if cached result is still valid."""
    cache_file = Path(f"results/.cache/{model}_app{app_number}.json")
    
    if not cache_file.exists():
        return False, None
    
    with open(cache_file) as f:
        cache_data = json.load(f)
    
    # Check age
    cached_time = datetime.fromisoformat(cache_data['timestamp'])
    age = datetime.now() - cached_time
    
    if age > timedelta(hours=max_age_hours):
        return False, None
    
    # Check code hash
    app_path = Path(f"generated/apps/{model}/app{app_number}")
    current_hash = get_code_hash(app_path)
    
    if current_hash != cache_data['code_hash']:
        return False, None
    
    return True, cache_data['result']

async def cached_analysis(model, app_number, force=False):
    """Run analysis with caching."""
    if not force:
        valid, result = is_cache_valid(model, app_number)
        if valid:
            print(f"✅ Using cached result for {model} app{app_number}")
            return result
    
    print(f"🔍 Running fresh analysis for {model} app{app_number}")
    manager = AnalyzerManager()
    result = await manager.run_static_analysis(model, app_number)
    
    # Cache result
    cache_dir = Path("results/.cache")
    cache_dir.mkdir(exist_ok=True)
    
    app_path = Path(f"generated/apps/{model}/app{app_number}")
    cache_data = {
        'timestamp': datetime.now().isoformat(),
        'code_hash': get_code_hash(app_path),
        'result': result
    }
    
    cache_file = cache_dir / f"{model}_app{app_number}.json"
    with open(cache_file, 'w') as f:
        json.dump(cache_data, f, indent=2)
    
    return result
```

---

## 🔥 Error Recovery

### Automatic Retry Logic

```python
#!/usr/bin/env python3
"""Retry failed analyses with exponential backoff."""

import asyncio
from analyzer.analyzer_manager import AnalyzerManager

async def retry_analysis(model, app, max_retries=3, base_delay=60):
    """Retry analysis with exponential backoff."""
    manager = AnalyzerManager()
    
    for attempt in range(max_retries):
        try:
            print(f"Attempt {attempt + 1}/{max_retries} for {model} app{app}")
            result = await manager.run_comprehensive_analysis(model, app)
            print(f"✅ Success on attempt {attempt + 1}")
            return result
            
        except Exception as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)  # Exponential backoff
                print(f"❌ Failed: {e}")
                print(f"⏳ Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
            else:
                print(f"❌ Failed after {max_retries} attempts")
                raise

# Usage
if __name__ == '__main__':
    asyncio.run(retry_analysis('openai_gpt-4', 1))
```

### Partial Result Recovery

```python
#!/usr/bin/env python3
"""Recover partial results from failed analyses."""

import json
from pathlib import Path

def recover_partial_results(model, app_number, task_id):
    """Extract usable data from failed analysis."""
    task_dir = Path(f"results/{model}/app{app_number}/task_{task_id}")
    
    if not task_dir.exists():
        print("❌ Task directory not found")
        return None
    
    # Check for service snapshots
    service_dir = task_dir / "services"
    if not service_dir.exists():
        print("❌ No service snapshots found")
        return None
    
    partial_results = {}
    
    for snapshot_file in service_dir.glob("*_snapshot.json"):
        service_name = snapshot_file.stem.replace('_snapshot', '')
        
        try:
            with open(snapshot_file) as f:
                data = json.load(f)
            partial_results[service_name] = data
            print(f"✅ Recovered {service_name} results")
        except Exception as e:
            print(f"❌ Could not recover {service_name}: {e}")
    
    if partial_results:
        # Save recovered results
        recovery_file = task_dir / "recovered_results.json"
        with open(recovery_file, 'w') as f:
            json.dump(partial_results, f, indent=2)
        print(f"💾 Saved recovered results to: {recovery_file}")
        return partial_results
    
    return None

# Usage
if __name__ == '__main__':
    recover_partial_results('openai_gpt-4', 1, 'task_a1b2c3d4')
```

---

## 🔍 Advanced Filtering

### Query Builder

```python
#!/usr/bin/env python3
"""Advanced task filtering and querying."""

from datetime import datetime, timedelta
from app import create_app
from app.models import AnalysisTask

app = create_app()

def advanced_task_query(
    status=None,
    model=None,
    analysis_type=None,
    min_findings=None,
    max_findings=None,
    date_from=None,
    date_to=None,
    has_errors=False
):
    """Build complex query for analysis tasks."""
    with app.app_context():
        query = AnalysisTask.query
        
        if status:
            query = query.filter(AnalysisTask.status == status)
        
        if model:
            query = query.filter(AnalysisTask.target_model.like(f'%{model}%'))
        
        if analysis_type:
            query = query.filter(AnalysisTask.analysis_type == analysis_type)
        
        if has_errors:
            query = query.filter(AnalysisTask.error_message.isnot(None))
        
        if date_from:
            query = query.filter(AnalysisTask.created_at >= date_from)
        
        if date_to:
            query = query.filter(AnalysisTask.created_at <= date_to)
        
        tasks = query.order_by(AnalysisTask.created_at.desc()).all()
        
        # Filter by findings count (requires parsing result_summary JSON)
        if min_findings is not None or max_findings is not None:
            filtered_tasks = []
            for task in tasks:
                if task.result_summary:
                    try:
                        summary = json.loads(task.result_summary)
                        findings = summary.get('total_findings', 0)
                        
                        if min_findings and findings < min_findings:
                            continue
                        if max_findings and findings > max_findings:
                            continue
                        
                        filtered_tasks.append(task)
                    except:
                        pass
            
            return filtered_tasks
        
        return tasks

# Usage examples
if __name__ == '__main__':
    # Find all failed security analyses in last 7 days
    date_from = datetime.now() - timedelta(days=7)
    failed_security = advanced_task_query(
        status='failed',
        analysis_type='security',
        date_from=date_from
    )
    print(f"Found {len(failed_security)} failed security analyses")
    
    # Find analyses with high finding counts
    high_findings = advanced_task_query(
        min_findings=50,
        model='gpt-4'
    )
    print(f"Found {len(high_findings)} analyses with 50+ findings")
```

---

**Last Updated**: November 4, 2025  
**Version**: 2.0.0  
**Related**: [Analysis Workflow](ANALYSIS_WORKFLOW.md), [Analyzer README](../analyzer/README.md)
