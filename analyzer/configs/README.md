# Analyzer Configuration Files

This folder contains configuration files for all analyzer tools. These configs are dynamically loaded by the analyzer services and can be overridden at runtime via the analysis wizard.

## Directory Structure

```
configs/
├── README.md                 # This file
├── defaults.json            # Master defaults & tool registry
├── static/                  # Static analyzer configs
│   ├── semgrep.yaml        # Semgrep rulesets
│   ├── mypy.ini            # MyPy strict type checking
│   ├── ruff.toml           # Ruff linter configuration
│   ├── eslint.config.json  # ESLint + TypeScript security rules
│   ├── bandit.yaml         # Bandit security scanner
│   ├── pylint.toml         # Pylint configuration
│   └── vulture.toml        # Vulture dead code detection
├── dynamic/                 # Dynamic analyzer configs
│   ├── zap.yaml            # OWASP ZAP scanning config
│   └── nmap.yaml           # Nmap port/service scanning
└── performance/            # Performance tester configs
    ├── load_test.yaml      # Load testing parameters
    └── aiohttp.yaml        # Async HTTP client settings
```

## Configuration Override Priority

1. **Runtime Override** (highest): Config passed via analysis wizard/API
2. **Custom Config File**: User-specified config file path
3. **Default Config Files**: Files in this `configs/` folder
4. **Hardcoded Defaults** (lowest): Built-in tool defaults

## Usage

### From Analysis Wizard

The analysis wizard allows per-tool configuration that overrides these defaults:

```javascript
// Example: Override semgrep rulesets
{
  "semgrep": {
    "rulesets": ["p/security-audit", "p/python", "p/flask"],
    "severity_threshold": "INFO"
  }
}
```

### From CLI

```bash
# Use custom config file
python analyzer/analyzer_manager.py analyze model 1 static --config myconfig.yaml

# Use specific tool config
python analyzer/analyzer_manager.py analyze model 1 static --tool-config semgrep:custom_semgrep.yaml
```

## Tool Configuration Reference

### Static Analysis Tools

| Tool | Config File | Key Settings |
|------|-------------|--------------|
| Semgrep | `static/semgrep.yaml` | Rulesets, severity threshold, excludes |
| MyPy | `static/mypy.ini` | Strictness level, plugins, ignore patterns |
| Ruff | `static/ruff.toml` | Rule selection, line length, target version |
| ESLint | `static/eslint.config.json` | Rules, TypeScript support, security plugins |
| Bandit | `static/bandit.yaml` | Skips, confidence, severity |
| Pylint | `static/pylint.toml` | Disabled checks, score threshold |
| Vulture | `static/vulture.toml` | Min confidence, whitelist |

### Dynamic Analysis Tools

| Tool | Config File | Key Settings |
|------|-------------|--------------|
| ZAP | `dynamic/zap.yaml` | Spider depth, scan type, timeout |
| Nmap | `dynamic/nmap.yaml` | Service detection, scripts, port range |

### Performance Tools

| Tool | Config File | Key Settings |
|------|-------------|--------------|
| Load Tests | `performance/load_test.yaml` | Users, duration, spawn rate |
| aiohttp | `performance/aiohttp.yaml` | Requests, concurrency |

## Adding New Tool Configurations

1. Create config file in appropriate subfolder
2. Update `defaults.json` with tool metadata
3. Update analyzer service to load config via `ConfigLoader`
4. Document configuration options in this README

## Validation

Configuration files are validated on load. Invalid configs fall back to defaults with a warning logged.
