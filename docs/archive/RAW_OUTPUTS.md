# Raw Tool Outputs Schema

This document explains how raw execution details from analyzer tools are captured and embedded in consolidated task result files under `results/<model_slug>/appN/analysis/`.

## Overview

Every consolidated task JSON (produced by `analyzer_manager.py save_task_results`) now includes a top‑level `raw_outputs` object. Each analyzer that ran (static, dynamic, performance, ai, security) contributes a sub‑object containing:

```
raw_outputs: {
  "dynamic": { ... },
  "performance": { ... },
  "static": { ... }
}
```

Within each analyzer section there is a `tools` map keyed by tool name (e.g. `curl`, `nmap`, `aiohttp`, `ab`, `locust`, `bandit`, `pylint`). Each tool entry attempts to unify these core fields:

| Field | Description |
|-------|-------------|
| status | success / error / timeout / not_available / partial |
| executed | Boolean flag (may be False if skipped or gated) |
| total_issues | Normalized issue or finding count (when applicable) |
| files_analyzed | For static tools: how many files were scanned |
| summary | Short textual summary (if provided by tool wrapper) |
| severity_breakdown | Map of severities (high/medium/low) -> counts |
| error | Error message when status != success |
| raw | Raw execution metadata (commands, stdout, stderr, timing) |

### Raw Execution Block

When available, `tool.raw` contains low‑level details:

```
"raw": {
  "command": ["ab", "-n", "100", "-c", "10", "http://.../"],   # Single primary command (if applicable)
  "stdout": "<truncated first 8k characters>",
  "stderr": "<truncated first 4k characters>",
  "exit_code": 0,
  "duration_seconds": 12.34,
  "commands": [                       # Multi‑invocation tools (dynamic curl, nmap wrapper)
     {
       "cmd": ["curl", "-I", "http://..."],
       "exit_code": 0,
       "duration": 0.42,
       "stdout": "HTTP/1.1 200 OK...",   # truncated to 2k chars
       "stderr": ""                     # truncated to 1k chars
     },
     ... up to 20 entries ...
  ]
}
```

Truncation limits (env overridable):
- `stdout` per command: 2000 chars
- `stderr` per command: 1000 chars
- Top‑level `stdout`: 8000 chars (static/perf) or 12000 for some perf tools (ab)
- Top‑level `stderr`: 4000 chars
- Maximum commands captured per tool: 20

### Environment Overrides

| Variable | Default | Effect |
|----------|---------|--------|
| `FULL_RAW_OUTPUTS` | 1 | If `0`, suppresses embedding large `issues` / `results` arrays (only summaries kept) |
| `RAW_OUTPUT_MAX_ISSUES` | 50 | Caps per‑tool issue list length; appends a truncation marker entry |

### Dynamic Analyzer Instrumentation

The dynamic analyzer wraps all subprocess invocations (`curl`, `nmap`, etc.) with a unified `_exec` helper that records:
- Command (list form)
- Exit code
- Duration (seconds)
- Captured stdout/stderr (truncated)

These are stored under an internal `tool_runs` map which the manager flattens into `raw_outputs.dynamic.tools`.

### Performance Analyzer Instrumentation

The performance tester produces:
- Per‑URL sections (connectivity, aiohttp, ab, locust)
- A synthesized `tool_runs` map containing each tool’s primary metrics & raw block
- Optional summary map `tool_results` (short form)

The manager aggregates `tool_runs` and also the summary `tool_results` ensuring consistent appearance in `raw_outputs.performance.tools`.

### Static / Security Tools

Static tools (bandit, pylint, flake8, etc.) may not always expose raw subprocess details. When available, the adapter sets a `raw` object (command, stdout, stderr). Otherwise only summary data appears.

### Universal Minimal Results

If `UNIVERSAL_RESULTS=1`, an additional minimized universal file is written (see `universal_results.py`). Raw command detail is still preserved in the main consolidated task file when `raw_outputs_included` is true.

### Troubleshooting Missing Raw Data

| Symptom | Likely Cause | Resolution |
|---------|--------------|-----------|
| `raw_outputs.performance.tools` empty | Manager consumed only first websocket frame (progress) | Ensure current `analyzer_manager.py` with multi‑frame loop is deployed & containers rebuilt |
| Tool present but no `raw` block | Tool not instrumented or produced no stdout | Confirm instrumentation wrapper exists; verify command actually ran |
| Commands truncated too aggressively | Defaults limiting size | Adjust env variables (stdout still capped intentionally) |
| `status: unknown` for analyzer | Analyzer final result frame not received | Check container logs; verify websocket did not close prematurely |

### Adding a New Tool

1. In the analyzer service: wrap execution with a recorder producing at least: `status`, `tool`, `executed`, `raw` (command, stdout, stderr, exit_code, duration).
2. Insert entry into the service’s `tool_runs` map (or embed directly in the `results` tree).
3. Rebuild containers (e.g. `pwsh ./rebuild_analyzers.ps1`).
4. Run an analysis and inspect the latest consolidated file under `results/.../analysis/`.

### Example Snippet (Dynamic Curl Tool Entry)

```
"curl": {
  "status": "success",
  "executed": true,
  "total_issues": 0,
  "raw": {
    "commands": [
      {"cmd": ["curl", "-I", "http://host.docker.internal:3001"], "exit_code": 0, "duration": 0.37, "stdout": "HTTP/1.1 200 OK..."}
    ]
  }
}
```

## File Naming & Location

Consolidated task files follow:
```
results/<model_slug>/app<NUM>/analysis/<model_slug>_app<NUM>_<task|analysis>_<timestamp>.json
```
Look for `raw_outputs` at the top level.

## Change Log (Raw Output System)

| Date | Change |
|------|--------|
| 2025-09 | Added dynamic analyzer per-command capture (tool_runs) |
| 2025-09 | Added performance analyzer raw capture & summary integration |
| 2025-09 | Manager multi-frame websocket receiving (prevents early truncation) |
| 2025-09 | Added aggregation of `tool_results` into raw output tools map |

## Future Enhancements
- Optional compression of very large stdout blocks
- Structured parsing (e.g., convert `ab` stdout into metrics table) stored alongside raw
- Redaction hook for secrets in stdout (API keys, tokens)

---
Questions or improvements? Open an issue or update this document.
