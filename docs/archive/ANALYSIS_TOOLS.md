# Analysis Tools Reference

Comprehensive documentation for the **15 analysis tools** integrated across **4 analyzer service containers** in the ThesisApp unified analysis platform. This document covers all tools in the static, dynamic, performance, and AI analyzer services.

> Unified Registry Note (September 2025): All tools described here are now sourced from the single `UnifiedToolRegistry` (`src/app/engines/unified_registry.py`). Numeric IDs used by the UI/API are deterministic (alphabetical ordering) and aliases like `zap-baseline` or `requirements-analyzer` automatically resolve to their canonical tool names (`zap`, `requirements-scanner`). When adding a new tool, register it once (container metadata) and it becomes immediately available across orchestrator, engines, and task execution without additional alias patches.

## Unified Analysis System Overview

ThesisApp implements a **unified analysis system** that coordinates execution of all 15 tools across 4 containerized analyzer services:

- **Static Analyzer** (port 2001): 8 tools for code quality and security
- **Dynamic Analyzer** (port 2002): 3 tools for runtime security testing
- **Performance Tester** (port 2003): 3 tools for load and performance testing
- **AI Analyzer** (port 2004): 1 tool for intelligent code review

## Tool Distribution by Container

### Static Analysis Tools (8 tools)
**Container**: `static-analyzer:2001`
1. **Bandit** - Python security vulnerability scanner
2. **PyLint** - Python code quality and style analysis
3. **ESLint** - JavaScript/TypeScript linting and security
4. **Safety** - Python dependency vulnerability detection
5. **Semgrep** - Multi-language static analysis security scanner
6. **MyPy** - Python static type checking
7. **JSHint** - JavaScript code quality analysis
8. **Vulture** - Python dead code detection

### Dynamic Analysis Tools (3 tools)
**Container**: `dynamic-analyzer:2002`
9. **ZAP** - OWASP web application security scanner
10. **cURL** - HTTP connectivity and security header analysis
11. **Nmap** - Network port scanning and service discovery

### Performance Testing Tools (3 tools)
**Container**: `performance-tester:2003`
12. **Locust** - Modern scalable load testing framework
13. **Apache Bench (ab)** - HTTP server performance benchmarking
14. **aiohttp** - Asynchronous HTTP response time measurement

### AI Analysis Tools (1 tool)
**Container**: `ai-analyzer:2004`
15. **Requirements Scanner** - AI-powered code review and analysis

## Table of Contents

- [Static Analysis Tools](#static-analysis-tools)
  - [Bandit (Python Security)](#bandit-python-security)
  - [Pylint (Python Code Quality)](#pylint-python-code-quality)
  - [ESLint (JavaScript/TypeScript)](#eslint-javascripttypescript)
  - [Stylelint (CSS)](#stylelint-css)
- [Dynamic Analysis Tools](#dynamic-analysis-tools)
  - [OWASP ZAP (Security Testing)](#owasp-zap-security-testing)
  - [cURL (Connectivity Testing)](#curl-connectivity-testing)
  - [Nmap (Port Scanning)](#nmap-port-scanning)
- [Performance Testing Tools](#performance-testing-tools)
  - [Apache Bench (Load Testing)](#apache-bench-load-testing)
  - [Locust (Load Testing)](#locust-load-testing)
  - [aiohttp (Async HTTP Testing)](#aiohttp-async-http-testing)
- [AI Analysis Tools](#ai-analysis-tools)
  - [OpenRouter API (AI Code Analysis)](#openrouter-api-ai-code-analysis)
- [Tool Configuration Guide](#tool-configuration-guide)
- [Output Format Reference](#output-format-reference)

---

## Static Analysis Tools

### Bandit (Python Security)

**Service**: `static-analyzer`  
**Purpose**: Security vulnerability detection in Python code  
**Official Website**: https://bandit.readthedocs.io/

#### Description
Bandit is a tool designed to find common security issues in Python code. It builds an Abstract Syntax Tree (AST) from Python code and runs appropriate plugins against the AST nodes to identify security vulnerabilities.

#### Key Features
- **Security-focused**: Identifies common Python security issues
- **AST-based analysis**: Deep code analysis through AST parsing
- **Configurable severity levels**: Low, Medium, High severity filtering
- **Confidence levels**: Report filtering based on confidence levels
- **Multiple output formats**: JSON, XML, CSV, HTML, YAML, text
- **Baseline comparison**: Compare against previous scans
- **Plugin architecture**: Extensible with custom security checks

#### Command Line Usage
```bash
# Basic scan
bandit -r /path/to/code

# JSON output with high severity only
bandit -r /path/to/code -f json --severity-level=high

# Skip specific tests
bandit -r /path/to/code -s B101,B601

# Exclude directories
bandit -r /path/to/code -x tests,docs
```

#### Configuration Options
- **Format options**: `csv`, `custom`, `html`, `json`, `sarif`, `screen`, `txt`, `xml`, `yaml`
- **Severity levels**: `all`, `low`, `medium`, `high`
- **Confidence levels**: `all`, `low`, `medium`, `high`
- **Test selection**: Include/exclude specific security tests
- **Context lines**: Number of code lines to display for each issue

#### ThesisApp Integration
In the static analyzer service, Bandit is configured with:
- JSON output format for structured results
- Configurable exclude directories (node_modules, .git, etc.)
- Custom skip patterns (B101 by default)
- Support for custom configuration files
- Timeout protection (120 seconds)

#### Sample Output Structure
```json
{
  "metrics": {
    "total_loc": 1500,
    "total_nosec": 2
  },
  "results": [
    {
      "filename": "app.py",
      "issue_confidence": "HIGH",
      "issue_severity": "MEDIUM",
      "issue_text": "Use of assert detected",
      "line_number": 42,
      "line_range": [42],
      "test_id": "B101",
      "test_name": "assert_used"
    }
  ]
}
```

#### Common Security Issues Detected
- **B101**: Assert statements in production code
- **B102**: `exec` usage
- **B103**: File permissions set to world-writable
- **B104**: Hardcoded passwords
- **B105**: Hardcoded password strings
- **B106**: Hardcoded password function arguments
- **B107**: Test for missing host key checking
- **B601**: Shell injection vulnerabilities
- **B602**: Subprocess with shell=True
- **B701**: Use of jinja2 autoescape=False

---

### Pylint (Python Code Quality)

**Service**: `static-analyzer`  
**Purpose**: Python code quality analysis and style checking  
**Official Website**: https://pylint.pycqa.org/

#### Description
Pylint is a comprehensive Python static analysis tool that checks for errors, enforces coding standards, looks for code smells, and provides suggestions for code improvements.

#### Key Features
- **Code quality analysis**: Detects bugs, design issues, and code smells
- **Style checking**: Enforces PEP 8 and custom coding standards
- **Refactoring suggestions**: Identifies areas for code improvement
- **Metrics calculation**: Complexity, maintainability scores
- **Customizable rules**: Disable/enable specific checks
- **Multiple output formats**: Text, JSON, parseable, colorized
- **Integration-friendly**: Works with IDEs and CI/CD systems

#### Command Line Usage
```bash
# Basic analysis
pylint mymodule.py

# JSON output
pylint --output-format=json mymodule.py

# Custom configuration
pylint --rcfile=.pylintrc mymodule.py

# Disable specific warnings
pylint --disable=C0103,W0622 mymodule.py

# Multiple output formats
pylint --output-format=json:report.json,colorized mymodule.py
```

#### Configuration Options
- **Output formats**: `text`, `parseable`, `colorized`, `json`, `json2`, `msvs`, `github`
- **Message categories**: 
  - `[I]` Informational
  - `[R]` Refactor suggestions
  - `[C]` Convention violations
  - `[W]` Warnings
  - `[E]` Errors
  - `[F]` Fatal errors
- **Scoring**: 0-10 quality score calculation
- **Reports**: Detailed analysis reports with metrics

#### ThesisApp Integration
In the static analyzer service, Pylint is configured with:
- JSON output format for structured parsing
- Custom .pylintrc generation with project-specific rules
- File limit protection (max 10 files to prevent timeouts)
- Timeout protection (120 seconds)
- Configurable disable rules for common false positives

#### Sample Configuration
```ini
[MAIN]
jobs=0
load-plugins=

[MESSAGES CONTROL]
disable=missing-docstring,too-few-public-methods

[REPORTS]
output-format=json
reports=no
score=yes

[FORMAT]
max-line-length=100
max-module-lines=1000

[DESIGN]
max-args=5
max-attributes=7
max-bool-expr=5
max-branches=12
max-locals=15
```

#### Sample Output Structure
```json
[
  {
    "type": "convention",
    "module": "mymodule",
    "obj": "MyClass",
    "line": 15,
    "column": 4,
    "endLine": 15,
    "endColumn": 12,
    "path": "mymodule.py",
    "symbol": "invalid-name",
    "message": "Variable name 'x' doesn't conform to snake_case naming style",
    "message-id": "C0103"
  }
]
```

---

### ESLint (JavaScript/TypeScript)

**Service**: `static-analyzer`  
**Purpose**: JavaScript and TypeScript linting and code quality  
**Official Website**: https://eslint.org/

#### Description
ESLint is a static analysis tool for identifying and reporting patterns in JavaScript/TypeScript code. It helps maintain code quality and consistency across projects.

#### Key Features
- **Pluggable architecture**: Extensible with custom rules and plugins
- **Configurable rules**: Enable/disable and customize rule behavior
- **Auto-fixing**: Automatically fix many code style issues
- **TypeScript support**: Full TypeScript analysis with @typescript-eslint
- **Framework support**: React, Vue, Angular integrations
- **Multiple parsers**: Babel, TypeScript, Acorn parsers
- **Output formats**: Stylish, JSON, checkstyle, JUnit, and more

#### Command Line Usage
```bash
# Basic linting
eslint file.js

# JSON output
eslint --format json file.js

# Auto-fix issues
eslint --fix file.js

# Custom configuration
eslint --config .eslintrc.json file.js

# Multiple files with output to file
eslint --format json --output-file results.json src/
```

#### Configuration Options
- **Output formats**: `stylish`, `json`, `compact`, `checkstyle`, `junit`, `html`, `tap`
- **Environments**: `browser`, `node`, `es6`, `jest`, `mocha`
- **Parser options**: ECMAScript version, source type, features
- **Rules**: 200+ built-in rules with customizable severity
- **Plugins**: Extend functionality with community plugins

#### ThesisApp Integration
In the static analyzer service, ESLint is configured with:
- JSON output format for structured results
- Temporary configuration file generation
- Support for JavaScript, JSX, TypeScript, TSX, Vue files
- Default security-focused rules
- Configurable ignore patterns
- Timeout protection (90 seconds)

#### Sample Configuration
```json
{
  "extends": ["eslint:recommended"],
  "env": {
    "browser": true,
    "es2021": true,
    "node": true
  },
  "parserOptions": {
    "ecmaVersion": 2021,
    "sourceType": "module",
    "ecmaFeatures": {
      "jsx": true
    }
  },
  "rules": {
    "no-eval": "error",
    "no-implied-eval": "error",
    "no-new-func": "error",
    "no-script-url": "error",
    "no-alert": "warn",
    "no-console": "warn",
    "no-debugger": "error",
    "no-unused-vars": "warn"
  },
  "ignorePatterns": ["node_modules", "dist", "build"]
}
```

#### Sample Output Structure
```json
[
  {
    "filePath": "/path/to/file.js",
    "messages": [
      {
        "ruleId": "no-unused-vars",
        "severity": 1,
        "message": "'unusedVar' is defined but never used.",
        "line": 5,
        "column": 7,
        "nodeType": "Identifier",
        "source": "const unusedVar = 42;",
        "endLine": 5,
        "endColumn": 16
      }
    ],
    "errorCount": 0,
    "warningCount": 1,
    "fixableErrorCount": 0,
    "fixableWarningCount": 0
  }
]
```

---

### Stylelint (CSS)

**Service**: `static-analyzer`  
**Purpose**: CSS and SCSS style linting  
**Official Website**: https://stylelint.io/

#### Description
Stylelint is a mighty CSS linter that helps avoid errors and enforce coding conventions in stylesheets.

#### Key Features
- **CSS validation**: Syntax and semantic error detection
- **Style enforcement**: Consistent formatting and conventions
- **Preprocessor support**: SCSS, Sass, Less support
- **Plugin ecosystem**: Extensive plugin library
- **Auto-fixing**: Automatic code formatting
- **Modern CSS**: Supports latest CSS features

#### Command Line Usage
```bash
# Basic linting
stylelint "src/**/*.css"

# JSON output
stylelint --formatter json "src/**/*.css"

# Auto-fix
stylelint --fix "src/**/*.css"
```

#### ThesisApp Integration
Basic integration with JSON output format and timeout protection.

---

## Dynamic Analysis Tools

### OWASP ZAP (Security Testing)

**Service**: `dynamic-analyzer`  
**Purpose**: Web application security testing  
**Official Website**: https://www.zaproxy.org/

#### Description
OWASP ZAP (Zed Attack Proxy) is an open-source web application security scanner. It's designed to be used by both beginners and experienced security professionals.

#### Key Features
- **Automated scanning**: Automatic vulnerability detection
- **Active scanning**: Actively tests for vulnerabilities
- **Passive scanning**: Monitors traffic for issues
- **Spidering**: Crawls applications to map attack surface
- **API support**: REST API for automation
- **Fuzzing**: Built-in fuzzer for input validation testing
- **Session management**: Handles complex authentication scenarios

#### Key Capabilities
- **Vulnerability detection**: XSS, SQL injection, CSRF, etc.
- **Authentication testing**: Session management analysis
- **API testing**: REST, SOAP, GraphQL support
- **Report generation**: Multiple output formats
- **Proxy functionality**: Intercepts and modifies traffic

#### Command Line Usage
```bash
# API scan with OpenAPI spec
zap-api-scan.py -t https://api.example.com/openapi.json -f openapi

# Baseline scan
zap-baseline.py -t https://example.com

# Custom configuration
zap-api-scan.py -t https://api.example.com/openapi.json -f openapi -c custom-rules.conf

# JSON output
zap-api-scan.py -t https://api.example.com/openapi.json -f openapi -j report.json
```

#### Configuration Options
- **Scan types**: `baseline`, `full`, `api`
- **Formats**: `openapi`, `soap`, `graphql`
- **Output formats**: `html`, `json`, `xml`, `markdown`
- **Rule levels**: `PASS`, `IGNORE`, `INFO`, `WARN`, `FAIL`
- **Authentication**: Support for various auth methods

#### ThesisApp Integration
In the dynamic analyzer service, ZAP integration includes:
- **Enhanced daemon management**: Automatic ZAP process lifecycle
- **Browser automation**: Firefox/Chrome integration for AJAX spidering
- **Source code mapping**: Maps vulnerabilities to source files
- **OAST integration**: Out-of-band Application Security Testing
- **Advanced configuration**: Addon management and integrity checking
- **Code context extraction**: Shows vulnerable code snippets with line numbers
- **Results caching**: JsonResultsManager for persistent storage
- **Network utilities**: Smart port allocation and connectivity checks
- **File utilities**: Source code discovery and binary detection
- **Progress monitoring**: Real-time scan progress with rate limiting
- **Enhanced reporting**: Detailed vulnerability categorization
- **Session management**: Complex authentication scenarios
- **API testing**: REST, SOAP, GraphQL endpoint analysis

#### Sample Usage in ThesisApp
```python
from zapv2 import ZAPv2

# Connect to ZAP daemon
zap = ZAPv2(apikey=api_key, proxies={'http': 'http://localhost:8090'})

# Spider scan
spider_id = zap.spider.scan(target_url)

# Active scan
ascan_id = zap.ascan.scan(target_url)

# Get alerts
alerts = zap.core.alerts(baseurl=target_url)
```

#### Sample Output Structure
```json
{
  "status": "success",
  "tool": "zap",
  "target": "https://example.com",
  "alert_counts": {
    "High": 2,
    "Medium": 5,
    "Low": 12,
    "Informational": 8
  },
  "total_alerts": 27,
  "alerts_sample": [
    {
      "alert": "Cross Site Scripting (Reflected)",
      "risk": "High",
      "confidence": "Medium",
      "url": "https://example.com/search?q=<script>alert(1)</script>",
      "param": "q",
      "description": "Cross-site Scripting (XSS) is an attack technique..."
    }
  ]
}
```

---

### cURL (Connectivity Testing)

**Service**: `dynamic-analyzer`  
**Purpose**: HTTP connectivity and basic response analysis  
**Official Website**: https://curl.se/

#### Description
cURL is a command-line tool for transferring data using various network protocols. In ThesisApp, it's used for basic connectivity testing and security header analysis.

#### Key Features
- **Protocol support**: HTTP, HTTPS, FTP, and more
- **Header inspection**: View HTTP headers and responses
- **Authentication**: Support for various auth methods
- **SSL/TLS support**: Certificate validation and encryption
- **Timeout controls**: Configure connection and transfer timeouts

#### ThesisApp Usage
```bash
# Connectivity test with headers only
curl -I --connect-timeout 10 --max-time 30 https://example.com

# Test specific paths
curl -I --connect-timeout 5 --max-time 10 https://example.com/admin
```

#### Security Header Analysis
ThesisApp analyzes responses for security headers:
- `X-Frame-Options`
- `X-Content-Type-Options`
- `Strict-Transport-Security`
- `Content-Security-Policy`
- `X-XSS-Protection`

---

### Nmap (Port Scanning)

**Service**: `dynamic-analyzer`  
**Purpose**: Network port scanning and service discovery  
**Official Website**: https://nmap.org/

#### Description
Nmap (Network Mapper) is a network discovery and security auditing tool used to discover hosts and services on a network.

#### Key Features
- **Port scanning**: TCP, UDP, and other protocols
- **Service detection**: Identify running services
- **OS detection**: Operating system fingerprinting
- **Script scanning**: NSE (Nmap Scripting Engine)

#### ThesisApp Usage
```bash
# Basic port scan
nmap -p 80,443,8080,3000,5000,8000 --open -T4 target-host

# Fast scan of common ports
nmap -p 1-1000 --open target-host
```

---

## Performance Testing Tools

### Apache Bench (Load Testing)

**Service**: `performance-tester`  
**Purpose**: HTTP server performance benchmarking  
**Official Website**: https://httpd.apache.org/docs/2.4/programs/ab.html

#### Description
Apache Bench (ab) is a tool for benchmarking HTTP web servers. It's designed to give an impression of how your current Apache installation performs.

#### Key Features
- **Simple load testing**: Easy-to-use command-line interface
- **Concurrent requests**: Configurable concurrency levels
- **Connection reuse**: HTTP Keep-Alive support
- **Authentication**: Basic and digest authentication
- **SSL support**: HTTPS testing capabilities
- **Detailed metrics**: Response times, transfer rates, percentiles

#### Command Line Usage
```bash
# Basic load test
ab -n 1000 -c 10 http://example.com/

# With keep-alive
ab -k -n 1000 -c 10 http://example.com/

# Custom headers
ab -n 100 -c 5 -H "Authorization: Bearer token" http://api.example.com/

# Time-limited test
ab -t 60 -c 10 http://example.com/

# Output to file
ab -n 100 -c 10 -g results.tsv http://example.com/
```

#### Configuration Options
- **Requests**: `-n` total number of requests
- **Concurrency**: `-c` concurrent requests
- **Time limit**: `-t` maximum time for testing
- **Keep-alive**: `-k` enable HTTP Keep-Alive
- **Headers**: `-H` custom HTTP headers
- **Authentication**: `-A` basic authentication
- **Cookies**: `-C` custom cookies
- **Content-Type**: `-T` for POST requests
- **Verbosity**: `-v` output level (0-4)

#### ThesisApp Integration
In the performance tester service, Apache Bench is configured with:
- Configurable request count and concurrency
- HTTP Keep-Alive support
- Custom headers and authentication
- Timeout protection
- Detailed connection time analysis
- CSV and HTML output support

#### Sample Configuration in ThesisApp
```python
{
  "apache_bench": {
    "requests": 100,
    "concurrency": 10,
    "timeout": 30,
    "keep_alive": True,
    "headers": {
      "User-Agent": "ThesisApp-Performance-Tester",
      "Accept": "application/json"
    },
    "csv_output": True
  }
}
```

#### Sample Output Structure
```json
{
  "status": "success",
  "tool": "apache_bench",
  "url": "http://example.com/",
  "test_parameters": {
    "total_requests": 100,
    "concurrency": 10,
    "timeout": 30,
    "keep_alive": true
  },
  "metrics": {
    "requests_per_second": 45.67,
    "time_per_request_mean": 21.89,
    "time_per_request_concurrent": 2.189,
    "transfer_rate_kb_sec": 1234.5,
    "failed_requests": 0,
    "complete_requests": 100
  },
  "connection_times": {
    "connect": {"min": 5, "mean": 12, "median": 10, "max": 45},
    "processing": {"min": 150, "mean": 200, "median": 180, "max": 350},
    "waiting": {"min": 140, "mean": 190, "median": 170, "max": 340},
    "total": {"min": 155, "mean": 212, "median": 190, "max": 395}
  }
}
```

#### Metrics Explanation
- **Requests per second**: Throughput measure
- **Time per request (mean)**: Average time for single request
- **Time per request (concurrent)**: Average time across all concurrent requests
- **Transfer rate**: Data transfer speed in KB/sec
- **Connection times**:
  - **Connect**: Time to establish TCP connection
  - **Processing**: Time to process request and generate response
  - **Waiting**: Time waiting for response after sending request
  - **Total**: Overall request completion time

---

### Locust (Load Testing)

**Service**: `performance-tester`  
**Purpose**: Scalable load testing with Python  
**Official Website**: https://locust.io/

#### Description
Locust is a modern load testing tool that allows you to define user behavior with Python code and swarm your system with millions of simultaneous users.

#### Key Features
- **Python-based**: Write test scenarios in Python
- **Distributed testing**: Scale across multiple machines
- **Web-based UI**: Real-time monitoring and control
- **Realistic user simulation**: Complex user behavior modeling
- **Event-driven**: Asynchronous and efficient
- **Extensible**: Custom protocols and behaviors

#### Command Line Usage
```bash
# Basic headless test
locust --headless -u 50 -r 10 -t 30s -H http://example.com

# With CSV output
locust --headless -u 50 -r 10 -t 30s --csv results -H http://example.com

# Custom locustfile
locust -f custom_test.py --headless -u 100 -r 20 -t 60s -H http://api.example.com
```

#### Configuration Options
- **Users**: `-u` number of concurrent users
- **Spawn rate**: `-r` users spawned per second
- **Run time**: `-t` test duration
- **Host**: `-H` target host
- **CSV output**: `--csv` prefix for CSV files
- **Headless mode**: `--headless` for automated testing

#### ThesisApp Integration
In the performance tester service, Locust is configured with:
- **Advanced execution modes**: Both CLI and library-based testing
- **Custom user classes**: Dynamic user behavior generation
- **Graph generation**: Visual performance metrics and charts
- **Results management**: JsonResultsManager for standardized storage
- **Concurrent testing**: Thread-safe execution with locks
- **Enhanced monitoring**: Real-time progress tracking and stats
- **Template generation**: Automatic locustfile creation from endpoints
- **Artifact management**: Organized test reports and CSV outputs
- **Caching**: Load previous results to avoid re-running tests
- **Background execution**: Long-running tests with progress monitoring

#### Sample Locustfile (Auto-generated)
```python
from locust import HttpUser, task, between

class QuickUser(HttpUser):
    wait_time = between(0.5, 1.5)
    
    @task
    def index(self):
        self.client.get('/')
```

#### Sample Output Structure
```json
{
  "status": "success",
  "tool": "locust",
  "url": "http://example.com",
  "config_used": {
    "users": 15,
    "spawn_rate": 3,
    "run_time": "15s"
  },
  "summary": {
    "requests_per_second": 23.45,
    "p95_response_time_ms": 450.0,
    "average_response_time_ms": 180.5,
    "total_requests": 352,
    "failures": 2
  }
}
```

---

### aiohttp (Async HTTP Testing)

**Service**: `performance-tester`  
**Purpose**: Asynchronous HTTP client for response time measurement  
**Official Website**: https://docs.aiohttp.org/

#### Description
aiohttp is a Python library for asynchronous HTTP client/server programming. In ThesisApp, it's used for measuring response times and concurrent load testing.

#### Key Features
- **Async/await support**: Modern Python asynchronous programming
- **Connection pooling**: Efficient connection reuse
- **Session management**: Persistent connections and cookies
- **Timeout control**: Fine-grained timeout configuration
- **SSL support**: HTTPS with certificate validation

#### ThesisApp Usage
The performance tester uses aiohttp for:
- **Response time measurement**: Accurate timing of HTTP requests
- **Concurrent testing**: Multiple simultaneous requests
- **Fallback connectivity**: Docker host gateway support
- **Error handling**: Detailed error reporting and retry logic

#### Sample Usage in ThesisApp
```python
async def measure_response_time(url, num_requests=10):
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        for i in range(num_requests):
            start_time = datetime.now()
            async with session.get(url) as response:
                await response.read()
                end_time = datetime.now()
                response_time = (end_time - start_time).total_seconds() * 1000
```

---

## Unified Analysis Configuration

### Tool Selection and Coordination

The unified analysis system automatically coordinates execution across all 4 containers:

```python
# Unified analysis configuration
unified_config = {
    "analysis_mode": "unified",
    "tools_by_service": {
        "static-analyzer": [1, 2, 3, 4, 5, 6, 7, 8],    # 8 static tools
        "dynamic-analyzer": [9, 10, 11],                # 3 dynamic tools  
        "performance-tester": [12, 13, 14],             # 3 performance tools
        "ai-analyzer": [15]                             # 1 AI tool
    },
    "service_to_engine_mapping": {
        "static-analyzer": "security",
        "dynamic-analyzer": "dynamic", 
        "performance-tester": "performance",
        "ai-analyzer": "security"  # AI tools routed through security engine
    }
}
```

### Container Tool Registry

All 15 tools are managed through the `ContainerToolRegistry`:

```python
from app.engines.container_tool_registry import get_container_tool_registry

registry = get_container_tool_registry()
all_tools = registry.get_all_tools()  # Returns all 15 tools

# Tools by container
static_tools = registry.get_tools_by_container(AnalyzerContainer.STATIC)      # 8 tools
dynamic_tools = registry.get_tools_by_container(AnalyzerContainer.DYNAMIC)    # 3 tools
perf_tools = registry.get_tools_by_container(AnalyzerContainer.PERFORMANCE)   # 3 tools
ai_tools = registry.get_tools_by_container(AnalyzerContainer.AI)              # 1 tool
```

### Execution Coordination

The unified analysis system coordinates parallel execution:

1. **Task Creation**: UI/API creates task with `unified_analysis=True`
2. **Tool Resolution**: All 15 tool IDs are resolved to names by container
3. **Engine Coordination**: Each container is mapped to its corresponding analysis engine
4. **Parallel Execution**: All 4 engines execute simultaneously
5. **Result Aggregation**: Results from all 15 tools are combined into unified output

### Service-to-Engine Mapping

```python
service_to_engine = {
    'static-analyzer': 'security',      # Handles 8 static analysis tools
    'dynamic-analyzer': 'dynamic',      # Handles 3 dynamic analysis tools
    'performance-tester': 'performance', # Handles 3 performance testing tools
    'ai-analyzer': 'security',          # AI tools routed through security engine
}
```

## Tool Coordination and Execution

### Unified Analysis Detection

The system automatically detects when to use unified analysis:

```python
# Detection logic in task execution service
is_unified_analysis = (
    meta.get('unified_analysis', False) or 
    meta.get('custom_options', {}).get('unified_analysis', False) or
    meta.get('tools_by_service', {}) or
    len(meta.get('selected_tool_names', [])) > 8  # Auto-detect based on tool count
)
```

### Container Health and Monitoring

All 4 analyzer containers are monitored for health:

```bash
# Container status check
docker-compose ps

# Expected output showing all 4 containers running:
# static-analyzer      running   0.0.0.0:2001->2001/tcp
# dynamic-analyzer     running   0.0.0.0:2002->2002/tcp
# performance-tester   running   0.0.0.0:2003->2003/tcp
# ai-analyzer          running   0.0.0.0:2004->2004/tcp
```

### Comprehensive Output Format

Unified analysis produces comprehensive results from all 15 tools:

```json
{
  "status": "completed",
  "tool_metrics": {
    "bandit": {"executed": true, "status": "success", "total_issues": 3},
    "pylint": {"executed": true, "status": "success", "total_issues": 12},
    "eslint": {"executed": true, "status": "success", "total_issues": 7},
    "safety": {"executed": true, "status": "success", "total_issues": 0},
    "semgrep": {"executed": true, "status": "success", "total_issues": 2},
    "mypy": {"executed": true, "status": "success", "total_issues": 4},
    "jshint": {"executed": true, "status": "success", "total_issues": 1},
    "vulture": {"executed": true, "status": "success", "total_issues": 0},
    "zap": {"executed": true, "status": "success", "total_issues": 5},
    "curl": {"executed": true, "status": "success", "total_issues": 2},
    "nmap": {"executed": true, "status": "success", "total_issues": 0},
    "locust": {"executed": true, "status": "success", "total_issues": 0},
    "ab": {"executed": true, "status": "success", "total_issues": 0},
    "aiohttp": {"executed": true, "status": "success", "total_issues": 0},
    "requirements-scanner": {"executed": true, "status": "success", "total_issues": 3}
  },
  "tools_used": [
    "bandit", "pylint", "eslint", "safety", "semgrep", "mypy", "jshint", "vulture",
    "zap", "curl", "nmap", "locust", "ab", "aiohttp", "requirements-scanner"
  ],
  "tools_skipped": [],  # No tools skipped in unified analysis
  "summary": {
    "tools_executed": 15,
    "services_executed": 4,
    "containers_utilized": ["static-analyzer", "dynamic-analyzer", "performance-tester", "ai-analyzer"]
  }
}
```

### Requirements Scanner (AI Code Analysis)

**Service**: `ai-analyzer`  
**Purpose**: AI-powered code review and analysis using advanced language models  
**Integration**: OpenRouter API with multiple model support

#### Description
The Requirements Scanner provides intelligent code analysis using state-of-the-art AI models. It performs comprehensive code review, identifies patterns, suggests improvements, and provides architectural insights that complement the static and dynamic analysis tools.

#### Key Features
- **Multi-model support**: Access to Claude, GPT-4, Gemini, and other leading AI models
- **Contextual analysis**: Deep understanding of code structure and business logic
- **Security insights**: AI-powered vulnerability detection beyond static analysis
- **Architecture review**: High-level design pattern analysis
- **Best practices**: Intelligent coding standard recommendations
- **Code quality assessment**: Holistic evaluation of maintainability and design

#### Supported AI Models
- **Anthropic**: `claude-3-haiku`, `claude-3-sonnet`, `claude-3-opus`
- **OpenAI**: `gpt-4o-mini`, `gpt-4o`, `gpt-3.5-turbo`
- **Google**: `gemini-flash-1.5`, `gemini-pro-1.5`
- **Meta**: `llama-3.1-8b-instruct`, `llama-3.1-70b-instruct`
- **Others**: Various models via OpenRouter API

#### Configuration Options
```python
{
  "requirements_scanner": {
    "ai_model": "anthropic/claude-3-haiku",
    "temperature": 0.1,
    "max_tokens": 500,
    "confidence_threshold": 0.7,
    "analysis_depth": "standard",
    "focus_areas": ["security", "performance", "maintainability"]
  }
}
```

#### ThesisApp Integration
The Requirements Scanner is seamlessly integrated into the unified analysis system:

- **Container**: Runs in `ai-analyzer:2004` container
- **Engine routing**: Processed through the security analysis engine
- **Coordination**: Executes in parallel with other tool categories
- **Result integration**: AI insights combined with static/dynamic analysis results

#### Sample Analysis Output
```json
{
  "requirements-scanner": {
    "status": "success",
    "execution_time": 25.8,
    "model_used": "anthropic/claude-3-haiku",
    "analysis_insights": {
      "security_findings": [
        {
          "severity": "medium",
          "category": "input_validation",
          "description": "User input not properly sanitized in authentication module",
          "file": "app/auth.py",
          "recommendation": "Implement input validation and sanitization"
        }
      ],
      "code_quality": {
        "overall_score": 7.8,
        "maintainability": "good",
        "complexity": "moderate",
        "test_coverage": "needs_improvement"
      },
      "architecture_review": {
        "patterns_used": ["MVC", "Repository"],
        "suggestions": ["Consider implementing dependency injection"],
        "scalability_concerns": ["Database connection pooling needed"]
      }
    },
    "tokens_used": {
      "input_tokens": 1247,
      "output_tokens": 456
    }
  }
}
```

---

## 12. Semgrep

**Purpose**: Multi-language static analysis for security and code quality  
**Service**: static-analyzer (port 2001)  
**Language Support**: 30+ languages (Python, JavaScript, Java, Go, C++, etc.)  
**Installation**: `pip install semgrep` or Docker image

### Command Line Usage
```bash
# Basic security scan
semgrep --config=auto --json /path/to/code

# Custom rules
semgrep --config=/path/to/rules.yml --json /path/to/code

# Specific rule sets
semgrep --config=p/security-audit --json /path/to/code
semgrep --config=p/owasp-top-ten --json /path/to/code

# Output to file
semgrep --config=auto --json --output=results.json /path/to/code

# SARIF format
semgrep --config=auto --sarif --output=results.sarif /path/to/code
```

### Configuration Options
- **--config**: Rule sets (auto, p/security-audit, p/owasp-top-ten, custom)
- **--severity**: Filter by severity (ERROR, WARNING, INFO)
- **--exclude**: Exclude files/directories
- **--timeout**: Maximum time per file
- **--max-memory**: Memory limit

### Output Format
```json
{
  "results": [
    {
      "check_id": "python.lang.security.audit.dangerous-system-call.dangerous-system-call",
      "path": "example.py",
      "start": {"line": 10, "col": 5},
      "end": {"line": 10, "col": 20},
      "message": "Found 'subprocess' call which can lead to arbitrary code execution",
      "severity": "ERROR",
      "metadata": {
        "cwe": "CWE-78: OS Command Injection",
        "owasp": "A03:2021 - Injection",
        "references": ["https://cwe.mitre.org/data/definitions/78.html"]
      },
      "extra": {
        "fingerprint": "abc123...",
        "is_ignored": false,
        "lines": "subprocess.call(user_input, shell=True)"
      }
    }
  ],
  "errors": [],
  "paths": {
    "scanned": ["/path/to/code"],
    "_comment": "..."
  }
}
```

### ThesisApp Integration
- Integrates with static-analyzer service for comprehensive SAST
- Provides 1500+ built-in rules for security and quality
- Supports custom rule creation for specific project needs
- Fast AST-based analysis with minimal false positives

---

## 13. Snyk Code

**Purpose**: Developer-first vulnerability scanner with AI-powered analysis  
**Service**: static-analyzer (port 2001)  
**Language Support**: JavaScript, TypeScript, Python, Java, C#, PHP, Go, etc.  
**Installation**: `npm install -g snyk` and authentication required

### Command Line Usage
```bash
# Authenticate with Snyk
snyk auth

# Code analysis
snyk code test --json

# Specific directory
snyk code test /path/to/code --json

# Filter by severity
snyk code test --severity-threshold=high --json

# Output to file
snyk code test --json > snyk-results.json

# SARIF format
snyk code test --sarif-file-output=results.sarif
```

### Configuration Options
- **--severity-threshold**: Filter by severity (low, medium, high, critical)
- **--exclude**: Exclude directories from analysis
- **--org**: Specify Snyk organization
- **--project-name**: Set project name for reporting
- **--all-projects**: Analyze all projects in directory

### Output Format
```json
{
  "runs": [
    {
      "results": [
        {
          "ruleId": "javascript/PT/rule",
          "level": "error",
          "message": {
            "text": "Prototype pollution vulnerability"
          },
          "locations": [
            {
              "physicalLocation": {
                "artifactLocation": {
                  "uri": "app.js"
                },
                "region": {
                  "startLine": 15,
                  "startColumn": 10,
                  "endLine": 15,
                  "endColumn": 25
                }
              }
            }
          ],
          "properties": {
            "security-severity": "8.5",
            "tags": ["security", "prototype-pollution"],
            "cwe": ["CWE-1321"]
          }
        }
      ]
    }
  ]
}
```

### ThesisApp Integration
- AI-powered vulnerability detection with low false positive rate
- Real-time scanning during development  
- Integration with CI/CD pipelines
- Detailed remediation guidance and fix suggestions
- **Enhanced authentication**: Automatic auth token handling
- **Project-specific analysis**: Custom project name and organization settings
- **SARIF export**: Industry-standard security report format
- **Threshold filtering**: Configurable severity-based filtering

---

## Enhanced Tool Features

### npm-audit (Enhanced)

**Enhanced Features in ThesisApp**:
- **Automated dependency installation**: Auto-runs `npm install` if needed
- **Package.json validation**: Checks for valid Node.js project structure  
- **Vulnerability categorization**: Maps npm severity to standardized levels
- **Fix suggestion integration**: Provides actionable remediation steps
- **Timeout protection**: Prevents hanging on large dependency trees

### Configuration Options (Enhanced)
```bash
# Enhanced npm-audit with auto-install
npm install --package-lock-only
npm audit --audit-level=moderate --json

# Production-only vulnerabilities
npm audit --production --json

# Skip development dependencies
npm audit --omit=dev --json
```

### Enhanced Output Processing
```json
{
  "auditReportVersion": 2,
  "vulnerabilities": {
    "package-name": {
      "name": "package-name",
      "severity": "high",
      "via": ["CVE-2021-12345"],
      "effects": ["dependent-package"],
      "range": "1.0.0 - 1.2.0",
      "nodes": ["node_modules/package-name"],
      "fixAvailable": {
        "name": "parent-package",
        "version": "2.0.0",
        "isSemVerMajor": true
      }
    }
  },
  "metadata": {
    "vulnerabilities": {
      "info": 0,
      "low": 1,
      "moderate": 2,
      "high": 3,
      "critical": 1,
      "total": 7
    }
  }
}
```

---

## 14. Mypy

**Purpose**: Static type checker for Python code  
**Service**: static-analyzer (port 2001)  
**Language Support**: Python  
**Installation**: `pip install mypy`

### Command Line Usage
```bash
# Basic type checking
mypy /path/to/python/code

# JSON output (processed via script)
mypy --show-error-codes --no-error-summary /path/to/code 2>&1 | python -c "
import json, sys, re
errors = []
for line in sys.stdin:
    if ':' in line and (' error:' in line or ' warning:' in line):
        parts = line.strip().split(':', 3)
        if len(parts) >= 4:
            errors.append({
                'file': parts[0],
                'line': int(parts[1]) if parts[1].isdigit() else 0,
                'column': int(parts[2]) if parts[2].isdigit() else 0,
                'message': parts[3].strip(),
                'severity': 'error' if ' error:' in line else 'warning'
            })
print(json.dumps({'results': errors}, indent=2))
"

# Specific configuration
mypy --config-file=mypy.ini /path/to/code

# Ignore missing imports
mypy --ignore-missing-imports /path/to/code
```

### Configuration Options
- **--strict**: Enable all optional checks
- **--ignore-missing-imports**: Skip missing third-party imports
- **--show-error-codes**: Include error codes in output
- **--no-error-summary**: Suppress summary statistics
- **--config-file**: Specify configuration file

### Output Format (Processed)
```json
{
  "results": [
    {
      "file": "example.py",
      "line": 25,
      "column": 10,
      "message": "error: Argument 1 to \"process\" has incompatible type \"str\"; expected \"int\"",
      "severity": "error",
      "code": "arg-type"
    },
    {
      "file": "example.py", 
      "line": 30,
      "column": 5,
      "message": "error: Function is missing a return type annotation",
      "severity": "error",
      "code": "no-untyped-def"
    }
  ],
  "summary": {
    "total_errors": 2,
    "files_checked": 1
  }
}
```

### ThesisApp Integration
- Validates Python type annotations and finds type-related bugs
- Integrates with static-analyzer for comprehensive Python analysis
- Helps catch runtime errors during static analysis phase
- Supports gradual typing adoption in existing codebases

---

## 15. Safety

**Purpose**: Python dependency vulnerability scanner  
**Service**: static-analyzer (port 2001)  
**Language Support**: Python dependencies  
**Installation**: `pip install safety`

### Command Line Usage
```bash
# Scan current environment
safety scan --output json

# Scan requirements file
safety scan --file requirements.txt --output json

# Save results to file
safety scan --output json > safety-results.json

# Check specific packages
safety scan --packages django==3.2.0 --output json

# Ignore specific vulnerabilities
safety scan --ignore 12345 --output json
```

### Configuration Options
- **--file**: Scan specific requirements file
- **--packages**: Check specific package versions
- **--ignore**: Ignore specific vulnerability IDs
- **--output**: Output format (json, text, bare)
- **--key**: API key for Safety DB Pro

### Output Format
```json
{
  "vulnerabilities": [
    {
      "vulnerability_id": "12345",
      "package_name": "django",
      "installed_version": "3.2.0",
      "vulnerable_spec": "<3.2.14",
      "vulnerability": "Django 3.2.x before 3.2.14 has a SQL injection vulnerability",
      "more_info_url": "https://safety.readthedocs.io/en/latest/",
      "advisory": "Update to Django 3.2.14 or later",
      "cve": "CVE-2022-28346"
    }
  ],
  "ignored_vulnerabilities": [],
  "metadata": {
    "safety_version": "3.2.10",
    "scan_target": "environment",
    "timestamp": "2025-01-16T10:30:00Z"
  },
  "announcements": []
}
```

### ThesisApp Integration
- Scans Python dependencies for known security vulnerabilities
- Integrates with static-analyzer for dependency security checks
- Provides CVE information and remediation guidance
- Supports both environment and requirements file scanning

---

## 16. Artillery

**Purpose**: Modern load testing and performance testing tool  
**Service**: performance-tester (port 2003)  
**Language Support**: HTTP/WebSocket testing via YAML configuration  
**Installation**: `npm install -g artillery`

### Command Line Usage
```bash
# Basic load test
artillery run --output test-results.json config.yml

# Quick test with custom settings
artillery quick --count 100 --num 10 http://localhost:3000

# Generate HTML report from JSON
artillery report test-results.json

# Debug mode
DEBUG=http artillery run config.yml

# Specific scenarios
artillery run --target http://localhost:3000 --phase-duration 60s config.yml
```

### Configuration Options (YAML)
```yaml
config:
  target: 'http://localhost:3000'
  phases:
    - duration: 300
      arrivalRate: 200
  processor: './payload.js'

scenarios:
  - flow:
    - get:
        url: '/api/health'
    - post:
        url: '/api/login'
        json:
          username: 'test'
          password: 'password'
```

### Output Format
```json
{
  "aggregate": {
    "timestamp": "2025-01-16T10:30:00.000Z",
    "scenariosCreated": 1000,
    "scenariosCompleted": 995,
    "requestsCompleted": 2985,
    "latency": {
      "min": 12,
      "max": 450,
      "median": 25,
      "p95": 85,
      "p99": 120
    },
    "rps": {
      "count": 2985,
      "mean": 99.5
    },
    "scenarioDuration": {
      "min": 50,
      "max": 500,
      "median": 75,
      "p95": 150,
      "p99": 200
    },
    "scenarioCounts": {
      "0": 995
    },
    "errors": {},
    "codes": {
      "200": 2800,
      "404": 185
    }
  },
  "intermediate": []
}
```

### ThesisApp Integration
- Modern alternative to Apache Bench for comprehensive load testing
- Supports complex scenarios with authentication and state management
- JSON output format for easy integration with analysis pipeline
- WebSocket testing capabilities for real-time applications

---

## 17. GPT4All

**Purpose**: Local AI model analysis for code review and requirement checking  
**Service**: ai-analyzer (port 2004)  
**Language Support**: Multiple (Python, JavaScript, etc.)  
**Installation**: GPT4All local server or API

### Command Line Usage
```bash
# Start GPT4All server
gpt4all serve --host localhost --port 4891

# API call for code analysis
curl -X POST "http://localhost:4891/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Llama 3 8B Instruct",
    "messages": [
      {
        "role": "system",
        "content": "You are an expert code reviewer. Analyze code and respond with JSON."
      },
      {
        "role": "user",
        "content": "Analyze this code for security issues: [code]"
      }
    ],
    "max_tokens": 4000,
    "temperature": 0.1
  }'
```

### Configuration Options
- **models**: Local AI models (Llama 3, Mistral, DeepSeek, GPT4o, Claude, etc.)
- **max_tokens**: Response length limit (typically 4000)
- **temperature**: Creativity control (0.0-1.0, typically 0.1 for analysis)
- **timeout**: Request timeout (default 30-120 seconds)
- **api_url**: Local server endpoint (default: http://localhost:4891/v1)

### Supported Models
- **Llama 3 8B Instruct** (preferred)
- **DeepSeek-R1-Distill-Qwen-7B**
- **Nous Hermes 2 Mistral DPO**
- **GPT4All Falcon**
- **Mistral 7B Instruct**

### Output Format
```json
{
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "{\"met\": true, \"confidence\": \"HIGH\", \"explanation\": \"Code implements proper input validation...\"}"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 245,
    "completion_tokens": 150,
    "total_tokens": 395
  }
}
```

### ThesisApp Integration
- **Local AI analysis**: Privacy-focused code analysis without external API calls
- **Requirement checking**: Validates code against specific functional requirements
- **Fallback analysis**: Basic pattern matching when AI unavailable
- **Code summarization**: Intelligent code reduction for large files
- **Multi-model support**: Automatic model selection and fallback
- **Caching**: Results stored using JsonResultsManager

---

## 18. JSHint

**Purpose**: JavaScript code quality and style checking  
**Service**: static-analyzer (port 2001)  
**Language Support**: JavaScript  
**Installation**: `npm install -g jshint`

### Command Line Usage
```bash
# Basic linting
jshint file.js

# JSON output
jshint --reporter json file.js

# Custom configuration
jshint --config .jshintrc file.js

# Multiple files
jshint src/**/*.js --reporter json

# Exclude patterns
jshint --exclude node_modules src/
```

### Configuration Options
- **reporter**: Output format (json, checkstyle, jslint)
- **config**: Configuration file path
- **exclude**: Exclude file patterns
- **extract**: Extract JavaScript from HTML files
- **verbose**: Show detailed error information

### Sample Configuration (.jshintrc)
```json
{
  "esversion": 6,
  "strict": true,
  "undef": true,
  "unused": true,
  "curly": true,
  "eqeqeq": true,
  "immed": true,
  "latedef": true,
  "newcap": true,
  "noarg": true,
  "sub": true,
  "boss": true,
  "eqnull": true,
  "browser": true,
  "node": true,
  "predef": ["$", "jQuery", "angular"]
}
```

### Output Format
```json
[
  {
    "id": "(error)",
    "raw": "Missing semicolon.",
    "evidence": "var x = 1",
    "line": 5,
    "character": 10,
    "scope": "(main)",
    "reason": "Missing semicolon.",
    "code": "W033"
  }
]
```

### ThesisApp Integration
- **Quality checking**: Detects JavaScript code quality issues
- **Style enforcement**: Enforces consistent coding standards
- **Legacy support**: Works with older JavaScript codebases
- **Lightweight**: Fast analysis for quick feedback
- **Configurable rules**: Customizable quality standards

---

## 19. Vulture

**Purpose**: Dead code detection in Python projects  
**Service**: static-analyzer (port 2001)  
**Language Support**: Python  
**Installation**: `pip install vulture`

### Command Line Usage
```bash
# Basic dead code detection
vulture path/to/code

# JSON output
vulture --min-confidence 80 path/to/code --json

# Exclude patterns
vulture path/to/code --exclude "*test*,*migrations*"

# Custom confidence threshold
vulture --min-confidence 60 path/to/code

# Sort by confidence
vulture --sort-by-size path/to/code
```

### Configuration Options
- **min-confidence**: Minimum confidence level (0-100)
- **exclude**: Exclude file/directory patterns
- **ignore-decorators**: Ignore decorated functions
- **ignore-names**: Ignore specific variable names
- **sort-by-size**: Sort results by file size
- **verbose**: Show additional information

### Output Format
```json
[
  {
    "filename": "example.py",
    "first_lineno": 15,
    "last_lineno": 20,
    "message": "unused function 'old_function'",
    "confidence": 90,
    "size": 6
  },
  {
    "filename": "utils.py",
    "first_lineno": 42,
    "last_lineno": 42,
    "message": "unused variable 'temp_var'",
    "confidence": 100,
    "size": 1
  }
]
```

### ThesisApp Integration
- **Code cleanup**: Identifies unused code for removal
- **Performance optimization**: Reduces codebase size
- **Maintenance**: Helps maintain clean, focused code
- **Quality metrics**: Provides code health insights
- **CI/CD integration**: Automated dead code detection

---

## Advanced Integration Features

### JsonResultsManager

The JsonResultsManager provides standardized result storage and retrieval across all analysis tools:

```python
# Initialize results manager
results_manager = JsonResultsManager(base_path=base_path, module_name="security")

# Save analysis results
results_manager.save_results(
    model="anthropic_claude-3.7-sonnet",
    app_num=1,
    results=analysis_data,
    file_name=".security_analysis.json"
)

# Load previous results
previous_results = results_manager.load_results(
    model="anthropic_claude-3.7-sonnet",
    app_num=1,
    file_name=".security_analysis.json"
)
```

### Tool Availability Checking

All analyzers implement intelligent tool availability detection:

```python
def _check_tool_availability(self, tool_name: str) -> bool:
    """Check if a tool is available in the system."""
    try:
        result = subprocess.run(
            [tool_name, '--version'],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False
```

### Thread-Safe Analysis

Concurrent analysis execution with thread safety:

```python
from threading import Lock

class SecurityAnalyzer:
    def __init__(self):
        self.analysis_lock = Lock()
    
    def run_analysis(self, model: str, app_num: int):
        with self.analysis_lock:
            # Thread-safe analysis execution
            return self._perform_analysis(model, app_num)
```

### Enhanced Error Handling

Standardized error handling and status reporting:

```python
# Status constants
STATUS_SUCCESS = "✅ No issues found"
STATUS_ISSUES_FOUND = "⚠️ Found {count} issues"
STATUS_ERROR = "❌ Error Reported"
STATUS_TIMEOUT = "❌ Timeout after {timeout}s"
STATUS_COMMAND_NOT_FOUND = "❌ Command not found"

# Tool result structure
class ToolResult(NamedTuple):
    issues: List[SecurityIssue]
    output: str
    status: str
```

### Source Code Mapping

Advanced vulnerability-to-source-code mapping:

```python
@dataclass
class CodeContext:
    snippet: str
    line_number: Optional[int] = None
    file_path: Optional[str] = None
    start_line: int = 0
    end_line: int = 0
    vulnerable_lines: List[int] = field(default_factory=list)
    highlight_positions: List[Tuple[int, int]] = field(default_factory=list)

def _get_affected_code(self, alert: Dict[str, Any]) -> Optional[CodeContext]:
    """Extract source code context for vulnerability."""
    # Implementation maps URLs to source files
    # Extracts code snippets with line numbers
    # Highlights vulnerable code sections
```

### Configuration Management

Advanced tool configuration with temporary files:

```python
@contextmanager
def _create_temp_config(self, prefix: str, config_content: dict, filename: str):
    """Create temporary configuration files for tools."""
    temp_file = None
    try:
        temp_file = tempfile.NamedTemporaryFile(
            mode='w', suffix=f'_{filename}', prefix=f'{prefix}_', delete=False
        )
        json.dump(config_content, temp_file, indent=2)
        temp_file.flush()
        yield Path(temp_file.name)
    finally:
        if temp_file and os.path.exists(temp_file.name):
            os.unlink(temp_file.name)
```

### Performance Optimization

**File Limits and Timeout Protection**:
```python
# Limit files to prevent timeouts
def _check_source_files(self, directory: Path, max_files: int = 30):
    source_files = list(directory.rglob('*.py'))[:max_files]
    return len(source_files) > 0, source_files

# Timeout protection for all tools
result = subprocess.run(
    command,
    capture_output=True,
    text=True,
    timeout=TOOL_TIMEOUT,  # 30-45 seconds
    cwd=working_directory
)
```

**Smart Analysis Caching**:
```python
def run_analysis(self, model: str, app_num: int, force_rerun: bool = False):
    # Check for cached results
    if not force_rerun:
        cached_results = self.load_previous_results(model, app_num)
        if cached_results:
            return cached_results
    
    # Run fresh analysis
    results = self._perform_analysis(model, app_num)
    self.save_results(model, app_num, results)
    return results
```

---

## Advanced Security Testing Features

### Browser Automation Integration

ThesisApp's ZAP integration includes sophisticated browser automation:

**Firefox Integration**:
```python
def _configure_browser_for_scanning(self) -> bool:
    """Configure Firefox for automated scanning."""
    firefox_binary = self._find_firefox_binary()
    if firefox_binary:
        # Configure Firefox profile for ZAP proxy
        # Set up SSL certificate handling
        # Configure proxy settings automatically
        return True
    return False
```

**Chrome Integration**:
```python
def _find_chrome_binary(self) -> Optional[str]:
    """Locate Chrome browser for automated testing."""
    possible_paths = [
        "C:/Program Files/Google/Chrome/Application/chrome.exe",
        "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
        "/usr/bin/google-chrome",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    ]
    return FileUtils.find_binary(possible_paths, "CHROME_BIN")
```

### OAST (Out-of-band Application Security Testing)

Advanced out-of-band vulnerability detection:

**OAST Configuration**:
```python
@log_operation("OAST service configuration")
def _configure_oast_service(self) -> bool:
    """Configure Out-of-band Application Security Testing."""
    if not self.oast_service_configured:
        callback_port = NetworkUtils.find_free_port(
            ZAPConfig.CALLBACK_PORT_RANGE[0],
            ZAPConfig.CALLBACK_PORT_RANGE[1]
        )
        
        # Set up OAST callback URL
        # Configure DNS and HTTP callbacks
        # Enable blind vulnerability detection
        
        self.callback_port = callback_port
        self.oast_service_configured = True
        return True
    return False
```

**OAST Capabilities**:
- **Blind SQL injection detection**
- **Server-side request forgery (SSRF) testing**
- **XML external entity (XXE) vulnerability detection**
- **DNS exfiltration testing**
- **HTTP callback verification**

### Network Utilities

Advanced network management for reliable testing:

```python
class NetworkUtils:
    @staticmethod
    @contextmanager
    def port_check(port: int):
        """Check if port is available and reserve it."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(('localhost', port))
            yield port
        except OSError:
            raise RuntimeError(f"Port {port} is not available")
        finally:
            sock.close()
    
    @staticmethod
    def find_free_port(start_port: int, max_port: int) -> int:
        """Find next available port in range."""
        for port in range(start_port, max_port + 1):
            try:
                with NetworkUtils.port_check(port):
                    return port
            except RuntimeError:
                continue
        raise RuntimeError(f"No free port found in range {start_port}-{max_port}")
```

### File and Binary Detection

Intelligent tool and binary discovery:

```python
class FileUtils:
    @staticmethod
    def find_binary(possible_paths: List[str], env_var: Optional[str] = None) -> Optional[str]:
        """Find binary executable across multiple paths."""
        # Check environment variable first
        if env_var and os.getenv(env_var):
            env_path = os.getenv(env_var)
            if os.path.isfile(env_path) and os.access(env_path, os.X_OK):
                return env_path
        
        # Check each possible path
        for path in possible_paths:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
                
        # Check system PATH
        binary_name = os.path.basename(possible_paths[0]) if possible_paths else None
        if binary_name:
            system_path = shutil.which(binary_name)
            if system_path:
                return system_path
        
        return None
```

---

## Tool Configuration Guide

### Adding New Tools

To add a new tool to the ThesisApp analyzer services:

1. **Detect Tool Availability**
   ```python
   def _detect_available_tools(self) -> List[str]:
       tools = []
       try:
           result = subprocess.run(['newtool', '--version'], 
                                 capture_output=True, text=True, timeout=10)
           if result.returncode == 0:
               tools.append('newtool')
       except Exception:
           pass
       return tools
   ```

2. **Add Tool Configuration**
   ```python
   async def analyze_with_newtool(self, source_path: Path, config: Dict) -> Dict:
       tool_config = config.get('newtool', {})
       cmd = ['newtool', '--format', 'json', str(source_path)]
       
       result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
       
       return {
           'tool': 'newtool',
           'status': 'success',
           'results': json.loads(result.stdout)
       }
   ```

3. **Update Tool Registry**
   Add tool definition to `_initialize_builtin_tools()` in `ToolRegistryService`:
   ```python
   {
       'name': 'newtool',
       'display_name': 'New Tool Scanner',
       'category': 'security',
       'service_name': 'static-analyzer',
       'description': 'New security scanning tool',
       'command': 'newtool --scan {source_path}',
       'compatibility': ['python', 'javascript'],
       'is_enabled': True,
       'estimated_duration': 90
   }
   ```

### Tool Selection and Gating

The analyzer services support tool selection via the `selected_tools` parameter:

```python
# Only run specific tools
selected_tools = ['bandit', 'eslint']
analysis_results = await analyze_model_code(
    model_slug, app_number, config, selected_tools=selected_tools
)
```

Tool gating is implemented at the service level:
```python
if selected_set is None or 'bandit' in selected_set:
    # Run Bandit analysis
    bandit_result = await analyze_with_bandit(source_path, config)
```

---

## Output Format Reference

### Standardized Output Structure

All tools in ThesisApp follow a standardized output structure:

```json
{
  "tool": "tool_name",
  "executed": true,
  "status": "success|error|timeout|no_issues",
  "total_issues": 0,
  "issues": [...],
  "config_used": {...},
  "error": "error_message",
  "metadata": {...}
}
```

### Status Values
- **`success`**: Tool executed successfully with results
- **`error`**: Tool execution failed with error
- **`timeout`**: Tool execution exceeded time limit
- **`no_issues`**: Tool executed successfully but found no issues
- **`tool_unavailable`**: Tool not installed or available

### Common Output Formats

#### JSON Format (Preferred)
All tools support JSON output for structured parsing:
```json
{
  "results": [...],
  "metadata": {...},
  "summary": {...}
}
```

#### CSV Format
Performance tools support CSV for data analysis:
```csv
timestamp,response_time,status_code,url
2025-01-16T10:30:45Z,245,200,https://example.com
```

#### XML Format
Some tools provide XML output:
```xml
<results>
  <issue severity="high">
    <description>Security vulnerability found</description>
    <location>file.py:42</location>
  </issue>
</results>
```

### Error Handling

All tools implement consistent error handling:
- **Timeout protection**: All tools have configurable timeouts
- **Resource limits**: Memory and CPU constraints
- **Graceful degradation**: Continue analysis if individual tools fail
- **Error reporting**: Detailed error messages and debugging info

---

## Best Practices

### Performance Optimization
- **File limits**: Restrict analysis to prevent timeouts
- **Parallel execution**: Run independent tools concurrently
- **Caching**: Cache tool results when appropriate
- **Resource monitoring**: Track memory and CPU usage

### Security Considerations
- **Input validation**: Sanitize all inputs to tools
- **Sandbox execution**: Run tools in isolated environments
- **Output sanitization**: Clean tool outputs before storage
- **Access controls**: Limit tool access to necessary files only

### Maintenance
- **Version management**: Track tool versions and compatibility
- **Configuration updates**: Keep tool configurations current
- **Documentation**: Maintain up-to-date tool documentation
- **Testing**: Regular testing of tool integrations

---

*Last updated: January 16, 2025*  
*For questions or updates to this documentation, please refer to the project maintainers.*

## Summary

This documentation now covers **19 analysis tools** and comprehensive integration features:

### Analysis Tools by Category:
- **Static Analysis (12 tools)**: Bandit, Pylint, ESLint, Stylelint, Semgrep, Snyk Code, Mypy, Safety, JSHint, Vulture
- **Dynamic Analysis (3 tools)**: OWASP ZAP (enhanced), cURL, Nmap  
- **Performance Testing (3 tools)**: Apache Bench, Locust (enhanced), Artillery
- **AI Analysis (2 tools)**: OpenRouter API, GPT4All (local)

### Advanced Integration Features:
- **JsonResultsManager**: Standardized result storage and retrieval
- **Thread-safe execution**: Concurrent analysis with proper locking
- **Tool availability checking**: Intelligent detection of installed tools
- **Enhanced error handling**: Comprehensive status reporting and recovery
- **Source code mapping**: Vulnerability-to-code correlation with line numbers
- **Browser automation**: Firefox/Chrome integration for advanced testing
- **OAST capabilities**: Out-of-band security testing for blind vulnerabilities
- **Smart caching**: Results persistence and reuse across sessions
- **Configuration management**: Temporary config files and advanced settings
- **Network utilities**: Intelligent port allocation and connectivity management
- **Performance optimization**: File limits, timeouts, and resource management

### Tool Selection and Execution:
- **Flexible tool selection**: Runtime tool filtering and gating
- **Fallback mechanisms**: Graceful degradation when tools unavailable
- **Timeout protection**: Prevents hanging analysis processes
- **Resource limits**: Memory and CPU constraints for stability
- **Progress monitoring**: Real-time status updates and logging

This comprehensive toolkit provides ThesisApp with industry-leading analysis capabilities across all dimensions of application security, performance, and code quality.