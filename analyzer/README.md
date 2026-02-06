# Unified Analyzer Manager

A comprehensive Python script for managing containerized analysis services and running various types of code analysis on AI-generated applications.

## Features

🐳 **Container Management**
- Start/stop/restart all analyzer services with Docker Compose
- Real-time status monitoring and health checks
- Comprehensive logging and error handling

🔍 **Analysis Capabilities**
- **Security Analysis**: Bandit, Safety, OWASP ZAP scanning
- **Performance Testing**: Locust-based load testing  
- **AI-Powered Analysis**: OpenRouter integration for code review
- **Static Code Analysis**: PyLint, ESLint, Flake8, etc.
- **Batch Processing**: Analyze multiple applications simultaneously

🚀 **Modern Architecture**
- Async WebSocket communication
- Type hints and dataclasses
- Structured logging and error handling
- Results management and reporting

## Recent Changes (Tool Normalization)

The analyzer services now emit a normalized `tool_results` map (where applicable) with per-tool objects including:

- `tool` (canonical tool name)
- `status` (`success | error | timeout | not_available | no_issues | completed`)
- `executed` (boolean)
- `total_issues` (count when applicable)

ESLint and JSHint traditionally exit with code `1` when lint findings are present. These exit codes are now interpreted as `success` when their JSON output parses correctly. Only process/infra failures (exit codes >1 or no usable output) are marked as `error`.

Performance and dynamic analyzers also provide standardized tool entries (`curl`, `nmap`, `zap`, `aiohttp`, `ab`, `locust`) so aggregation layers (e.g., universal results schema) no longer report false `not_available` statuses for tools that actually ran.

This normalization reduces false negatives and produces more reliable consolidated reporting.

### Result Directory Pruning

Legacy per-service result folders (`static-analyzer/`, `dynamic-analyzer/`, `performance-tester/`, `ai-analyzer/`, `security-analyzer/`) are now automatically pruned after each analysis. Only the consolidated `analysis/` directory is retained under `results/<model>/appN/`. Any stray legacy JSON artifacts will be removed to keep the structure consistent.

### SARIF Extraction (File Size Optimization)

SARIF data from static analysis tools (bandit, semgrep, pylint, ruff, flake8) is now **extracted to separate files** instead of being embedded in JSON results. This reduces file sizes by **60-80%**:

**Structure:**
- `results/{model}/app{N}/task_{id}/sarif/` - Directory containing extracted SARIF files
  - `static_bandit.sarif.json` - Bandit SARIF output
  - `static_semgrep.sarif.json` - Semgrep SARIF output  
  - `static_ruff.sarif.json` - Ruff SARIF output
  - `static_flake8.sarif.json` - Flake8 SARIF output
  - `static_consolidated.sarif.json` - Combined SARIF from all tools
  - `dynamic_consolidated.sarif.json` - Dynamic analysis SARIF (if applicable)

**JSON Result Format:**
```json
{
  "results": {
    "analysis": {
      "results": {
        "python": {
          "bandit": {
            "sarif_file": "sarif/static_bandit.sarif.json"  // Reference instead of embedded data
          }
        }
      }
    }
  }
}
```

**Benefits:**
- Consolidated results: ~30KB instead of ~8MB (73% reduction)
- Service snapshots: ~2MB instead of ~8MB (72% reduction)
- Faster file I/O and JSON parsing
- Easier to navigate result files
- SARIF files can be imported into security dashboards separately

**Migration:**
Existing bloated service snapshots can be migrated using:
```bash
python scripts/migrate_service_snapshots.py --dry-run  # Preview
python scripts/migrate_service_snapshots.py            # Execute
```

This applies to **both** consolidated task results and per-service snapshots.

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables (Optional)
```bash
# For AI analysis
export OPENROUTER_API_KEY="your_api_key_here"
```

### 3. Start Services
```bash
python analyzer_manager.py start
```

### 4. Run Analysis
```bash
# Single application
python analyzer_manager.py analyze anthropic_claude-3.7-sonnet 1

# Batch analysis
python analyzer_manager.py batch example_batch.json

# Quick batch on multiple models
python analyzer_manager.py batch-models openai_gpt-4,anthropic_claude-3.7-sonnet
```

## Command Reference

### Container Management
```bash
python analyzer_manager.py start                    # Start all services
python analyzer_manager.py stop                     # Stop all services
python analyzer_manager.py restart                  # Restart all services
python analyzer_manager.py status                   # Show service status
python analyzer_manager.py logs [service] [lines]   # Show logs
```

### Analysis Operations
```bash
# Single analysis
python analyzer_manager.py analyze <model> <app> [type]
# Types: comprehensive, security, ai, static

# Examples:
python analyzer_manager.py analyze anthropic_claude-3.7-sonnet 1 security
python analyzer_manager.py analyze openai_gpt-4 2 comprehensive

# Batch analysis from JSON file
python analyzer_manager.py batch models.json

# Quick batch on multiple models (app 1)
python analyzer_manager.py batch-models model1,model2,model3
```

#### Tool selection (optional)
You can gate which tools run for a given analysis using --tools. The list is service-specific and case-insensitive.

Examples:

```bash
# Run only Bandit (security via static-analyzer)
python analyzer_manager.py analyze anthropic_claude-3.7-sonnet 1 security --tools bandit

# Static analysis with only ESLint
python analyzer_manager.py analyze anthropic_claude-3.7-sonnet 1 static --tools eslint

# Dynamic analysis: run connectivity + nmap only (no ZAP)
python analyzer_manager.py analyze anthropic_claude-3.7-sonnet 1 dynamic --tools curl nmap

# Performance testing: only aiohttp built-ins, skip ab/locust
python analyzer_manager.py analyze anthropic_claude-3.7-sonnet 1 performance --tools aiohttp
```

### Testing & Health
```bash
python analyzer_manager.py test                     # Test all services
python analyzer_manager.py health                   # Check health
python analyzer_manager.py ping <service>           # Ping specific service
```

### Results Management
```bash
python analyzer_manager.py results                  # List recent results
python analyzer_manager.py results <filename>       # Show specific result
```

## Batch Analysis Format

Create a JSON file with model and app number pairs:

```json
[
    ["anthropic_claude-3.7-sonnet", 1],
    ["anthropic_claude-3.7-sonnet", 2], 
    ["openai_gpt-4", 1],
    ["openai_gpt-4", 2]
]
```

## Service Architecture

The analyzer consists of 4 containerized services (with replicas for concurrency):

- **static-analyzer** (port 2001, 4 replicas): Static code analysis with Bandit, Semgrep, PyLint, Ruff, ESLint
- **dynamic-analyzer** (port 2002, 3 replicas): OWASP ZAP security scanning, nmap, curl probes
- **performance-tester** (port 2003, 2 replicas): Locust-based load testing, aiohttp, Apache ab
- **ai-analyzer** (port 2004, 2 replicas): AI-powered code analysis via OpenRouter

## Results Structure

Analysis results are saved in the `results/` directory with timestamps:

```
results/
├── anthropic_claude-3.7-sonnet_app1_comprehensive_20250808_142301.json
├── batch_analysis_a1b2c3d4_20250808_143015.json
└── openai_gpt-4_app2_security_20250808_144520.json
```

Each result file includes:
- Metadata (model, app, timestamp, analyzer version)
- Detailed analysis results for each service
- Summary statistics and confidence scores

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENROUTER_API_KEY` | API key for AI analysis | Optional |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | Optional |

## Troubleshooting

### Services Won't Start
```bash
# Check Docker is running
docker --version

# Check Docker Compose
docker-compose --version

# View logs
python analyzer_manager.py logs
```

### WebSocket Connection Issues
```bash
# Check service health
python analyzer_manager.py health

# Test individual service
python analyzer_manager.py ping ai-analyzer

# Check port accessibility
python analyzer_manager.py status
```

### Static analyzer shows "opening handshake failed"
You may see stack traces from `websockets.server/http11` in the static-analyzer logs when a client connects and disconnects without sending an HTTP request line (e.g., port scans or non-WS probes). These are benign.

Mitigation: we reduced the log level for `websockets.server`, `websockets.http`, and `websockets.http11` inside the service to cut noise. Health checks and valid clients continue to work normally.

### Analysis Failures
```bash
# Run comprehensive tests
python analyzer_manager.py test

# Check specific service logs
python analyzer_manager.py logs security-analyzer 100

# Verify source path exists
ls ../misc/models/anthropic_claude-3.7-sonnet/app1/
```

## Examples

### Basic Workflow
```bash
# 1. Start infrastructure
python analyzer_manager.py start

# 2. Check everything is working
python analyzer_manager.py test

# 3. Run security analysis
python analyzer_manager.py analyze anthropic_claude-3.7-sonnet 1 security

# 4. View results
python analyzer_manager.py results

# 5. Stop when done
python analyzer_manager.py stop
```

### Batch Analysis Workflow
```bash
# 1. Create batch file
echo '[["model1", 1], ["model2", 1]]' > my_batch.json

# 2. Run batch analysis
python analyzer_manager.py batch my_batch.json

# 3. Monitor progress in logs
python analyzer_manager.py logs

# 4. Check results
python analyzer_manager.py results
```

## Integration

The unified analyzer can be integrated into larger workflows:

```python
from analyzer_manager import AnalyzerManager
import asyncio

async def main():
    manager = AnalyzerManager()
    
    # Start services programmatically
    manager.start_services()
    
    # Run analysis
    results = await manager.run_comprehensive_analysis("model_name", 1)
    
    # Process results
    print(f"Analysis complete: {results}")

asyncio.run(main())
```

## Build Script (Windows)

You can build all analyzer images with the included PowerShell script (tries analyzer_manager.py build first, then Docker Compose):

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -Command "& .\build.ps1"
```

Options:
- `-NoCache` Build images without cache
- `-Pull` Always attempt to pull newer base images
- `-LogPath` Custom log file path (default: logs/analyzer-build.log)

Example:
```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -Command "& .\build.ps1 -NoCache -Pull"
```

The build log is saved to `../logs/analyzer-build.log` (repo root logs folder).

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review service logs: `python analyzer_manager.py logs`
3. Test service health: `python analyzer_manager.py test`
4. Check Docker containers: `docker-compose ps`
