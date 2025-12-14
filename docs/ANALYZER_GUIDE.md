# Analyzer Services Guide

Detailed documentation for the containerized analyzer microservices.

## Overview

ThesisAppRework uses four Docker-based analyzer services:

| Service | Port | Purpose |
|---------|------|---------|
| Static Analyzer | 2001 | Code quality and security linting |
| Dynamic Analyzer | 2002 | Runtime security scanning |
| Performance Tester | 2003 | Load and stress testing |
| AI Analyzer | 2004 | AI-powered code review |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Flask Application                      │
│                    (Port 5000)                          │
└─────────────────────────┬───────────────────────────────┘
                          │ WebSocket
         ┌────────────────┼────────────────┐
         │                │                │
         ▼                ▼                ▼
    ┌─────────┐     ┌─────────┐     ┌─────────┐
    │ Static  │     │ Dynamic │     │  Perf   │
    │  2001   │     │  2002   │     │  2003   │
    └─────────┘     └─────────┘     └─────────┘
         │                │                │
         └────────────────┼────────────────┘
                          ▼
              ┌───────────────────────┐
              │  generated/apps/      │
              │  (mounted read-only)  │
              └───────────────────────┘
```

## Static Analyzer (Port 2001)

Performs code quality and security analysis without executing code.

### Tools

| Tool | Language | Purpose |
|------|----------|---------|
| Bandit | Python | Security vulnerabilities |
| Semgrep | Multi | Pattern-based security |
| Safety | Python | Dependency vulnerabilities |
| Pylint | Python | Code quality |
| Flake8 | Python | Style checking |
| Ruff | Python | Fast linting |
| MyPy | Python | Type checking |
| ESLint | JavaScript | JS/TS linting |
| JSHint | JavaScript | JS quality |

### Usage

```bash
# Run all static tools
python analyzer/analyzer_manager.py analyze openai_gpt-4 1 static

# Run specific tools
python analyzer/analyzer_manager.py analyze openai_gpt-4 1 static --tools bandit,eslint
```

### Output

Results are saved to `results/{model}/app{N}/task_{id}/services/static.json`:

```json
{
  "status": "completed",
  "tools": {
    "bandit": {
      "status": "success",
      "findings_count": 3,
      "sarif_file": "sarif/static_bandit.sarif.json"
    },
    "eslint": {
      "status": "success",
      "findings_count": 12
    }
  }
}
```

## Dynamic Analyzer (Port 2002)

Performs runtime security testing against running applications.

### Tools

| Tool | Purpose |
|------|---------|
| OWASP ZAP | Web vulnerability scanning |
| nmap | Port and service scanning |
| curl probes | HTTP endpoint testing |

### Prerequisites

The target application must be running. Dynamic analyzer connects to:
- `http://host.docker.internal:{port}` (from container)

### Usage

```bash
# Ensure app is running first
python analyzer/analyzer_manager.py analyze openai_gpt-4 1 dynamic
```

### Port Resolution

Ports are resolved in this order:
1. `.env` file in `generated/apps/{model}/app{N}/`
2. Database `PortConfiguration` model
3. `misc/port_config.json` fallback

## Performance Tester (Port 2003)

Load testing and performance benchmarking.

### Tools

| Tool | Purpose |
|------|---------|
| Locust | Distributed load testing |
| aiohttp | Async HTTP benchmarks |
| Apache ab | Basic load testing |

### Configuration

Default load test parameters:
- Users: 10 concurrent
- Duration: 60 seconds
- Spawn rate: 2 users/second

### Usage

```bash
python analyzer/analyzer_manager.py analyze openai_gpt-4 1 performance
```

### Output Metrics

- Requests per second (RPS)
- Response time percentiles (p50, p95, p99)
- Error rate
- Throughput (bytes/second)

## AI Analyzer (Port 2004)

AI-powered code analysis using LLM models.

### Features

- Requirements compliance checking
- Code quality assessment
- Security pattern detection
- Optimization suggestions

### Configuration

Requires `OPENROUTER_API_KEY` in environment.

### Usage

```bash
python analyzer/analyzer_manager.py analyze openai_gpt-4 1 ai
```

## Management Commands

### Start/Stop Services

```bash
# Start all analyzers
python analyzer/analyzer_manager.py start

# Stop all analyzers
python analyzer/analyzer_manager.py stop

# Restart specific service
docker restart static-analyzer
```

### Health Checks

```bash
# Check all services
python analyzer/analyzer_manager.py health

# Check specific service
python analyzer/analyzer_manager.py health static
```

### View Logs

```bash
# All logs
python analyzer/analyzer_manager.py logs

# Specific service (last 100 lines)
python analyzer/analyzer_manager.py logs static-analyzer 100
```

### Rebuild Containers

```bash
# Fast incremental rebuild
./start.ps1 -Mode Rebuild

# Clean rebuild (no cache)
./start.ps1 -Mode CleanRebuild
```

## Comprehensive Analysis

Run all analyzers in sequence:

```bash
python analyzer/analyzer_manager.py analyze openai_gpt-4 1 comprehensive
```

This executes:
1. Static analysis
2. Dynamic analysis (if app running)
3. Performance testing (if app running)
4. AI analysis

Results are consolidated into a single JSON file.

## Results Structure

```
results/{model}/app{N}/task_{id}/
├── {model}_app{N}_task_{id}_{timestamp}.json  # Consolidated
├── manifest.json                              # Metadata
├── sarif/                                     # SARIF files
│   ├── static_bandit.sarif.json
│   └── static_semgrep.sarif.json
└── services/                                  # Per-service
    ├── static.json
    ├── dynamic.json
    ├── performance.json
    └── ai.json
```

## Troubleshooting

### Container Won't Start

```bash
# Check Docker status
docker ps -a

# View container logs
docker logs static-analyzer

# Rebuild container
docker compose -f analyzer/docker-compose.yml build static-analyzer
```

### WebSocket Connection Failed

- Verify container is running: `docker ps`
- Check port is accessible: `curl http://localhost:2001/health`
- Review firewall settings

### Analysis Timeout

Increase timeout in `.env`:
```
STATIC_ANALYSIS_TIMEOUT=600
SECURITY_ANALYSIS_TIMEOUT=900
```

## Connection Resilience

The analyzer system implements robust connection handling (Dec 2025):

### Pre-flight Health Checks

Before starting analysis, the system verifies all required services are accessible:

```bash
# Manual health check
python analyzer/analyzer_manager.py health
```

### Retry with Exponential Backoff

WebSocket connections retry automatically:

| Attempt | Delay |
|---------|-------|
| 1 | Immediate |
| 2 | 2 seconds |
| 3 | 4 seconds |
| 4 | 8 seconds |

### Circuit Breaker

After 3 consecutive failures to a service, it enters a 5-minute cooldown:

| State | Behavior |
|-------|----------|
| CLOSED | Normal operation |
| OPEN | Requests fail immediately (cooldown) |
| HALF-OPEN | Test connection after cooldown |

Services automatically recover after cooldown or on first successful connection.

### Clear Error Messages

If services are down, errors clearly indicate:
- Which services are inaccessible
- How to start them: `python analyzer/analyzer_manager.py start`

## Container Rebuild Strategies

### Fast Incremental Rebuild

```bash
./start.ps1 -Mode Rebuild
```

- Uses BuildKit cache mounts
- Preserves pip/npm caches between builds
- Rebuilds only changed layers
- **Time**: 30-90 seconds

**Use for**: Code changes, minor dependency updates

### Clean Rebuild

```bash
./start.ps1 -Mode CleanRebuild
```

- No cache, full rebuild
- Pulls fresh base images
- Reinstalls all dependencies
- **Time**: 12-18 minutes

**Use for**: Major dependency changes, Dockerfile modifications, cache corruption

### BuildKit Optimizations

The analyzer Dockerfile uses cache mounts for faster rebuilds:

```dockerfile
# Persistent pip cache
RUN --mount=type=cache,target=/root/.cache/pip pip install ...

# Persistent npm cache
RUN --mount=type=cache,target=/root/.npm npm install ...
```

## Related

- [Architecture](ARCHITECTURE.md)
- [Background Services](BACKGROUND_SERVICES.md)
- [Development Guide](development-guide.md)
- [Troubleshooting](TROUBLESHOOTING.md)
