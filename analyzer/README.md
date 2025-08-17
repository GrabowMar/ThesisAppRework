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

The analyzer consists of 5 containerized services:

- **static-analyzer** (port 2001): Static code analysis with PyLint, Flake8, ESLint
- **dynamic-analyzer** (port 2002): OWASP ZAP security scanning  
- **performance-tester** (port 2003): Locust-based load testing
- **ai-analyzer** (port 2004): AI-powered code analysis via OpenRouter
- **security-analyzer** (port 2005): Security scanning with Bandit, Safety

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
