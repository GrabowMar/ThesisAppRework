# CLI Command Reference

> Complete reference for analyzer_manager.py commands

---

## Overview

The `analyzer_manager.py` CLI provides comprehensive management of the analysis system.

```bash
python analyzer/analyzer_manager.py <command> [options]
```

---

## Commands

### `start`

Start all analyzer services.

```bash
python analyzer/analyzer_manager.py start
```

**What it does**:
1. Starts Docker containers (static, dynamic, performance, ai, gateway)
2. Waits for health checks
3. Reports status

---

### `stop`

Stop all analyzer services.

```bash
python analyzer/analyzer_manager.py stop
```

---

### `restart`

Restart all analyzer services.

```bash
python analyzer/analyzer_manager.py restart
```

---

### `health`

Check health of all services.

```bash
python analyzer/analyzer_manager.py health
```

**Output**:
```
✓ Flask App       : http://localhost:5000         [OK]
✓ Redis           : redis://localhost:6379        [OK]
✓ Static Analyzer : http://localhost:2001         [OK]
✓ Dynamic Analyzer: http://localhost:2002         [OK]
✓ Performance     : http://localhost:2003         [OK]
✓ AI Analyzer     : http://localhost:2004         [OK]
✓ WebSocket       : ws://localhost:8765           [OK]
```

---

### `analyze`

Run analysis on a generated application.

```bash
python analyzer/analyzer_manager.py analyze <model> <app_num> [type] [options]
```

**Arguments**:
- `model` - Model slug (e.g., `anthropic_claude-3.5-sonnet`)
- `app_num` - Application number (1-30)
- `type` - Analysis type: `security`, `performance`, `quality`, `ai`, `all` (default: `all`)

**Options**:
- `--tools TOOL1,TOOL2` - Specific tools to run
- `--timeout SECONDS` - Override timeout (default: 300)
- `--force` - Overwrite existing results

**Examples**:
```bash
# Run all analysis types
python analyzer/analyzer_manager.py analyze anthropic_claude-3.5-sonnet 1

# Run specific type
python analyzer/analyzer_manager.py analyze anthropic_claude-3.5-sonnet 1 security

# Run specific tools
python analyzer/analyzer_manager.py analyze anthropic_claude-3.5-sonnet 1 custom --tools bandit,pylint

# With timeout
python analyzer/analyzer_manager.py analyze anthropic_claude-3.5-sonnet 1 --timeout 600
```

---

### `batch`

Run batch analysis from configuration file.

```bash
python analyzer/analyzer_manager.py batch <config_file>
```

**Config file format** (`batch.json`):
```json
[
  ["anthropic_claude-3.5-sonnet", 1],
  ["openai_gpt-4", 1],
  ["google_gemini-2.0-flash-exp", 1]
]
```

**Example**:
```bash
python analyzer/analyzer_manager.py batch batch_analysis.json
```

---

### `results`

View analysis results.

```bash
python analyzer/analyzer_manager.py results [options]
```

**Options**:
- `--model MODEL` - Filter by model
- `--app NUM` - Filter by app number
- `--format FORMAT` - Output format: `json`, `csv`, `html` (default: `json`)
- `--output FILE` - Save to file

**Examples**:
```bash
# View all results
python analyzer/analyzer_manager.py results

# View specific app results
python analyzer/analyzer_manager.py results --model anthropic_claude-3.5-sonnet --app 1

# Export to CSV
python analyzer/analyzer_manager.py results --format csv --output report.csv
```

---

### `list`

List generated applications.

```bash
python analyzer/analyzer_manager.py list [options]
```

**Options**:
- `--model MODEL` - Filter by model
- `--status STATUS` - Filter by status

**Example**:
```bash
python analyzer/analyzer_manager.py list --status running
```

---

### `logs`

View analyzer service logs.

```bash
python analyzer/analyzer_manager.py logs [service] [lines]
```

**Arguments**:
- `service` - Service name (default: all services)
- `lines` - Number of lines (default: 50)

**Examples**:
```bash
# View all logs
python analyzer/analyzer_manager.py logs

# View specific service
python analyzer/analyzer_manager.py logs static-analyzer 100
```

---

## Port Manager CLI

Manage port allocations.

```bash
python scripts/port_manager.py <command> [options]
```

### Commands

#### `list`

List all port allocations.

```bash
python scripts/port_manager.py list
```

#### `check`

Check ports for specific model.

```bash
python scripts/port_manager.py check <model>
```

#### `stats`

Show port allocation statistics.

```bash
python scripts/port_manager.py stats
```

#### `release`

Release ports (dangerous!).

```bash
python scripts/port_manager.py release <model> <app_num>
```

---

## Last Updated

October 2025
