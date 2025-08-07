# Split Testing Interface Implementation Instructions

## Overview
This document provides comprehensive instructions for the next agent to implement a sophisticated three-page testing interface to replace the current unified security testing page. The implementation will split functionality into dedicated pages with extensive tool-specific configurations and detailed results displays.

## Current State Analysis

### Existing Architecture
- **Current Interface**: `unified_security_testing.html` - Single page with modals
- **Backend Routes**: Extensive API endpoints in `src/web_routes.py` under `testing_bp` blueprint
- **Containerized Services**: 5 testing services (security-scanner, performance-tester, zap-scanner, ai-analyzer, test-coordinator)
- **Database Models**: Full ORM models for job tracking, results, and configurations
- **Service Integration**: `UnifiedCLIAnalyzer` orchestrates all testing operations

### Available Testing Tools
1. **Security Scanner (Port 8001)**:
   - **Backend Tools**: Bandit, Safety, PyLint, Semgrep, Vulture
   - **Frontend Tools**: ESLint, retire.js, npm-audit
   - **Configurations**: Confidence levels, severity filtering, path exclusions

2. **Performance Tester (Port 8002)**:
   - **Load Testing**: Locust-based with configurable users, spawn rate, duration
   - **Test Types**: Load, stress, spike, volume testing
   - **Reporting**: JSON, HTML, CSV with detailed metrics

3. **ZAP Scanner (Port 8003)**:
   - **Scan Types**: Spider, Active, Passive, Baseline, API scans
   - **API Support**: OpenAPI, SOAP, GraphQL definitions
   - **Authentication**: Context-based authentication support
   - **Advanced Options**: Alpha rules, safe mode, debug output

4. **AI Analyzer (Port 8004)** - Currently disabled:
   - **Models**: GPT-4, Claude 3 Sonnet, Gemini Pro
   - **Analysis Types**: Requirements check, code quality, security focus

5. **Test Coordinator (Port 8005)**:
   - **Orchestration**: Multi-service test coordination
   - **Batch Operations**: Cross-model/app testing

## Implementation Plan

### Page 1: Test Creation Page (`/testing/create`)

#### Purpose
Replace the current modal with a comprehensive full-page test creation interface.

#### Features Required
1. **Tool Selection Wizard**:
   - Step-by-step configuration for each tool
   - Real-time validation and preview
   - Advanced option panels for power users

2. **Tool-Specific Configuration Panels**:

   **Bandit Configuration**:
   ```html
   <!-- Confidence Levels -->
   <select name="bandit_confidence">
     <option value="low">Low Confidence</option>
     <option value="medium" selected>Medium Confidence</option>
     <option value="high">High Confidence</option>
   </select>
   
   <!-- Severity Filtering -->
   <div class="severity-checkboxes">
     <input type="checkbox" name="bandit_severity" value="low" checked>
     <input type="checkbox" name="bandit_severity" value="medium" checked>
     <input type="checkbox" name="bandit_severity" value="high" checked>
   </div>
   
   <!-- Test Selection -->
   <textarea name="bandit_include_tests" placeholder="B101,B102,B103"></textarea>
   <textarea name="bandit_exclude_tests" placeholder="B404,B605"></textarea>
   
   <!-- Path Filtering -->
   <textarea name="bandit_exclude_paths" placeholder="*/tests/*,*/venv/*"></textarea>
   
   <!-- Output Format -->
   <select name="bandit_format">
     <option value="json" selected>JSON</option>
     <option value="xml">XML</option>
     <option value="txt">Text</option>
     <option value="csv">CSV</option>
   </select>
   
   <!-- Advanced Options -->
   <input type="checkbox" name="bandit_recursive" checked>
   <select name="bandit_aggregate">
     <option value="file">By File</option>
     <option value="vuln">By Vulnerability</option>
   </select>
   ```

   **Safety Configuration**:
   ```html
   <!-- Scan Type -->
   <select name="safety_check_type">
     <option value="scan" selected>Scan (v3)</option>
     <option value="check">Check (Legacy)</option>
   </select>
   
   <!-- Output Format -->
   <select name="safety_output_format">
     <option value="json" selected>JSON</option>
     <option value="html">HTML</option>
     <option value="spdx">SPDX</option>
     <option value="text">Text</option>
   </select>
   
   <!-- Detailed Output -->
   <input type="checkbox" name="safety_detailed_output" checked>
   
   <!-- Policy File -->
   <input type="file" name="safety_policy_file" accept=".json,.yml,.yaml">
   
   <!-- Auto-fix -->
   <input type="checkbox" name="safety_apply_fixes">
   
   <!-- Continue on Error -->
   <input type="checkbox" name="safety_continue_on_error" checked>
   ```

   **ZAP Configuration**:
   ```html
   <!-- Scan Type -->
   <select name="zap_scan_type">
     <option value="baseline" selected>Baseline Scan</option>
     <option value="active">Active Scan</option>
     <option value="api">API Scan</option>
     <option value="full">Full Scan</option>
   </select>
   
   <!-- Target URL -->
   <input type="url" name="zap_target_url" placeholder="http://localhost:3000" required>
   
   <!-- API Definition -->
   <input type="url" name="zap_api_definition" placeholder="OpenAPI/Swagger URL">
   <select name="zap_api_format">
     <option value="openapi">OpenAPI</option>
     <option value="soap">SOAP</option>
     <option value="graphql">GraphQL</option>
   </select>
   
   <!-- Advanced Options -->
   <input type="checkbox" name="zap_alpha_passive">
   <input type="checkbox" name="zap_safe_mode">
   <input type="checkbox" name="zap_debug">
   
   <!-- Reporting -->
   <select name="zap_format">
     <option value="json" selected>JSON</option>
     <option value="html">HTML</option>
     <option value="xml">XML</option>
     <option value="md">Markdown</option>
   </select>
   
   <!-- Scan Limits -->
   <input type="number" name="zap_max_time" min="0" placeholder="Maximum scan time (0=unlimited)">
   <input type="number" name="zap_passive_scan_delay" min="0" value="0">
   
   <!-- Minimum Alert Level -->
   <select name="zap_min_level">
     <option value="PASS">PASS</option>
     <option value="IGNORE">IGNORE</option>
     <option value="INFO">INFO</option>
     <option value="WARN" selected>WARN</option>
     <option value="FAIL">FAIL</option>
   </select>
   ```

   **Performance Testing Configuration**:
   ```html
   <!-- Test Type -->
   <select name="perf_test_type">
     <option value="load" selected>Load Test</option>
     <option value="stress">Stress Test</option>
     <option value="spike">Spike Test</option>
     <option value="volume">Volume Test</option>
   </select>
   
   <!-- Load Configuration -->
   <input type="number" name="perf_users" min="1" max="1000" value="10">
   <input type="number" name="perf_spawn_rate" min="0.1" max="100" step="0.1" value="2">
   <input type="number" name="perf_duration" min="10" max="3600" value="60">
   
   <!-- Target Configuration -->
   <input type="url" name="perf_target_url" placeholder="http://localhost:3000" required>
   
   <!-- Advanced Options -->
   <input type="checkbox" name="perf_web_ui" checked>
   <select name="perf_output_format">
     <option value="json" selected>JSON</option>
     <option value="html">HTML</option>
     <option value="csv">CSV</option>
   </select>
   
   <!-- Custom Headers -->
   <textarea name="perf_custom_headers" placeholder='{"Authorization": "Bearer token"}'></textarea>
   
   <!-- Request Patterns -->
   <textarea name="perf_request_patterns" placeholder="GET /api/users\nPOST /api/login"></textarea>
   ```

3. **Model & Application Selection**:
   - Multi-select interface for bulk testing
   - Model capability filtering
   - Application health status indicators

4. **Batch Configuration**:
   - Parallel execution settings
   - Timeout configurations
   - Failure handling options

#### Implementation Details

**Template Structure**:
```
src/templates/pages/
├── test_creation.html           # Main creation page
└── partials/testing/
    ├── tool_config_bandit.html     # Bandit configuration panel
    ├── tool_config_safety.html     # Safety configuration panel
    ├── tool_config_zap.html        # ZAP configuration panel
    ├── tool_config_performance.html # Performance configuration panel
    ├── tool_config_ai.html         # AI analysis configuration panel
    ├── model_selector.html         # Model/app selection component
    └── batch_options.html          # Batch configuration options
```

**Route Implementation**:
```python
@testing_bp.route("/create")
def test_creation_page():
    """Full-page test creation interface."""
    # Get all available models and applications
    # Get tool capabilities and configurations
    # Render comprehensive form
    
@testing_bp.route("/api/tool-config/<tool_name>")
def get_tool_configuration(tool_name):
    """Get tool-specific configuration panel via HTMX."""
    # Return tool-specific HTML fragment
    
@testing_bp.route("/api/validate-config", methods=["POST"])
def validate_configuration():
    """Validate configuration in real-time."""
    # Return validation results via HTMX
```

### Page 2: Test Management Page (`/testing/dashboard`)

#### Purpose
Central hub for managing active tests, service status, and historical data.

#### Features Required
1. **Service Management Panel**:
   - Real-time service health monitoring
   - Individual service start/stop/restart controls
   - Resource usage metrics (CPU, memory)
   - Service logs viewing

2. **Active Tests Section**:
   - Live test progress monitoring
   - Real-time status updates via WebSocket/HTMX
   - Test cancellation controls
   - Resource allocation display

3. **Test History**:
   - Filterable test history table
   - Advanced search and filtering
   - Batch operations (restart, delete, export)
   - Performance metrics overview

4. **Statistics Dashboard**:
   - Test success/failure rates
   - Tool usage statistics
   - Performance trends
   - Service reliability metrics

#### Implementation Details

**Template Structure**:
```
src/templates/pages/
├── test_dashboard.html          # Main dashboard page
└── partials/testing/
    ├── service_status.html         # Service monitoring panel
    ├── active_tests.html           # Active tests display
    ├── test_history.html           # Historical tests table
    ├── statistics_overview.html    # Stats dashboard
    └── service_logs.html          # Service logs viewer
```

### Page 3: Test Results & Details Page (`/testing/results/<test_id>`)

#### Purpose
Comprehensive test results display with tool-specific visualizations and detailed analysis.

#### Features Required

1. **Tool-Specific Result Displays**:

   **Bandit Results**:
   ```html
   <!-- Security Issue Summary -->
   <div class="security-summary">
     <div class="severity-breakdown">
       <span class="badge bg-danger">High: {{ high_count }}</span>
       <span class="badge bg-warning">Medium: {{ medium_count }}</span>
       <span class="badge bg-info">Low: {{ low_count }}</span>
     </div>
   </div>
   
   <!-- Issue Details Table -->
   <table class="table table-striped">
     <thead>
       <tr>
         <th>Severity</th>
         <th>Test ID</th>
         <th>File</th>
         <th>Line</th>
         <th>Issue</th>
         <th>Confidence</th>
       </tr>
     </thead>
     <tbody>
       {% for issue in bandit_issues %}
       <tr class="severity-{{ issue.severity }}">
         <td><span class="badge bg-{{ issue.severity }}">{{ issue.severity|title }}</span></td>
         <td><code>{{ issue.test_id }}</code></td>
         <td><code>{{ issue.filename }}</code></td>
         <td>{{ issue.line_number }}</td>
         <td>{{ issue.issue_text }}</td>
         <td>{{ issue.issue_confidence }}</td>
       </tr>
       {% endfor %}
     </tbody>
   </table>
   
   <!-- Code Snippets -->
   <div class="code-snippets">
     {% for issue in bandit_issues %}
     <div class="code-block">
       <h6>{{ issue.filename }}:{{ issue.line_number }}</h6>
       <pre><code class="language-python">{{ issue.code_snippet }}</code></pre>
       <div class="issue-details">
         <p><strong>Issue:</strong> {{ issue.issue_text }}</p>
         <p><strong>Severity:</strong> {{ issue.severity }}</p>
         <p><strong>Confidence:</strong> {{ issue.issue_confidence }}</p>
         {% if issue.more_info %}
         <a href="{{ issue.more_info }}" target="_blank">More Information</a>
         {% endif %}
       </div>
     </div>
     {% endfor %}
   </div>
   ```

   **ZAP Results**:
   ```html
   <!-- Vulnerability Summary -->
   <div class="vulnerability-summary">
     <div class="risk-breakdown">
       <div class="risk-item high">
         <span class="count">{{ zap_results.high_risk_count }}</span>
         <span class="label">High Risk</span>
       </div>
       <div class="risk-item medium">
         <span class="count">{{ zap_results.medium_risk_count }}</span>
         <span class="label">Medium Risk</span>
       </div>
       <div class="risk-item low">
         <span class="count">{{ zap_results.low_risk_count }}</span>
         <span class="label">Low Risk</span>
       </div>
       <div class="risk-item info">
         <span class="count">{{ zap_results.info_count }}</span>
         <span class="label">Informational</span>
       </div>
     </div>
   </div>
   
   <!-- Vulnerability Details -->
   {% for alert in zap_results.alerts %}
   <div class="vulnerability-card risk-{{ alert.risk|lower }}">
     <div class="card-header">
       <h5>{{ alert.name }}</h5>
       <div class="badges">
         <span class="badge bg-{{ alert.risk|lower }}">{{ alert.risk }} Risk</span>
         <span class="badge bg-secondary">{{ alert.confidence }} Confidence</span>
       </div>
     </div>
     <div class="card-body">
       <p><strong>Description:</strong> {{ alert.description }}</p>
       <p><strong>Solution:</strong> {{ alert.solution }}</p>
       {% if alert.reference %}
       <p><strong>Reference:</strong> <a href="{{ alert.reference }}" target="_blank">{{ alert.reference }}</a></p>
       {% endif %}
       
       <!-- Affected URLs -->
       <h6>Affected Instances:</h6>
       <ul class="instance-list">
         {% for instance in alert.instances %}
         <li>
           <code>{{ instance.uri }}</code>
           {% if instance.param %}
           <span class="param">Parameter: <code>{{ instance.param }}</code></span>
           {% endif %}
           {% if instance.evidence %}
           <div class="evidence">
             <strong>Evidence:</strong>
             <pre><code>{{ instance.evidence }}</code></pre>
           </div>
           {% endif %}
         </li>
         {% endfor %}
       </ul>
     </div>
   </div>
   {% endfor %}
   ```

   **Performance Results**:
   ```html
   <!-- Performance Metrics Summary -->
   <div class="performance-summary">
     <div class="metric-cards">
       <div class="metric-card">
         <div class="metric-value">{{ perf_results.avg_response_time }}ms</div>
         <div class="metric-label">Average Response Time</div>
       </div>
       <div class="metric-card">
         <div class="metric-value">{{ perf_results.requests_per_second }}</div>
         <div class="metric-label">Requests/Second</div>
       </div>
       <div class="metric-card">
         <div class="metric-value">{{ perf_results.failure_rate }}%</div>
         <div class="metric-label">Failure Rate</div>
       </div>
       <div class="metric-card">
         <div class="metric-value">{{ perf_results.total_requests }}</div>
         <div class="metric-label">Total Requests</div>
       </div>
     </div>
   </div>
   
   <!-- Response Time Chart -->
   <div class="chart-container">
     <canvas id="responseTimeChart"></canvas>
   </div>
   
   <!-- Request Distribution -->
   <div class="request-distribution">
     <h6>Request Distribution</h6>
     <table class="table">
       <thead>
         <tr>
           <th>Endpoint</th>
           <th>Requests</th>
           <th>Failures</th>
           <th>Avg Response Time</th>
           <th>Min/Max</th>
         </tr>
       </thead>
       <tbody>
         {% for endpoint in perf_results.endpoints %}
         <tr>
           <td><code>{{ endpoint.name }}</code></td>
           <td>{{ endpoint.num_requests }}</td>
           <td>{{ endpoint.num_failures }}</td>
           <td>{{ endpoint.avg_response_time }}ms</td>
           <td>{{ endpoint.min_response_time }}/{{ endpoint.max_response_time }}ms</td>
         </tr>
         {% endfor %}
       </tbody>
     </table>
   </div>
   ```

2. **Interactive Elements**:
   - Code syntax highlighting with Prism.js
   - Expandable/collapsible sections
   - Filter and search within results
   - Export functionality (PDF, JSON, CSV)

3. **Comparison Tools**:
   - Side-by-side result comparison
   - Historical trend analysis
   - Regression detection

#### Implementation Details

**Template Structure**:
```
src/templates/pages/
├── test_results.html            # Main results page
└── partials/testing/results/
    ├── bandit_results.html         # Bandit-specific results
    ├── safety_results.html         # Safety-specific results
    ├── zap_results.html           # ZAP-specific results
    ├── performance_results.html    # Performance-specific results
    ├── ai_results.html            # AI analysis results
    ├── result_summary.html        # Overall test summary
    ├── export_options.html        # Export functionality
    └── comparison_view.html       # Result comparison tools
```

## Backend Implementation Requirements

### Route Updates

**New Routes Required**:
```python
# Test Creation Routes
@testing_bp.route("/create")
def test_creation_page()

@testing_bp.route("/api/tool-config/<tool_name>")
def get_tool_configuration(tool_name)

@testing_bp.route("/api/validate-config", methods=["POST"])
def validate_configuration()

# Dashboard Routes
@testing_bp.route("/dashboard")
def test_dashboard()

@testing_bp.route("/api/service-status")
def get_service_status()

@testing_bp.route("/api/active-tests")
def get_active_tests()

# Results Routes
@testing_bp.route("/results/<test_id>")
def test_results(test_id)

@testing_bp.route("/api/results/<test_id>/export")
def export_results(test_id)

@testing_bp.route("/api/results/compare")
def compare_results()
```

### Configuration Management

**Tool Configuration Storage**:
```python
# Extended database models for tool configurations
class ToolConfiguration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.String(50), db.ForeignKey('batch_job.id'))
    tool_name = db.Column(db.String(50), nullable=False)
    configuration = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Configuration validation schemas
TOOL_SCHEMAS = {
    'bandit': {
        'confidence': {'type': 'string', 'enum': ['low', 'medium', 'high']},
        'severity': {'type': 'array', 'items': {'enum': ['low', 'medium', 'high']}},
        'include_tests': {'type': 'string'},
        'exclude_tests': {'type': 'string'},
        'exclude_paths': {'type': 'string'},
        'format': {'type': 'string', 'enum': ['json', 'xml', 'txt', 'csv']},
        'recursive': {'type': 'boolean'},
        'aggregate': {'type': 'string', 'enum': ['file', 'vuln']}
    },
    'zap': {
        'scan_type': {'type': 'string', 'enum': ['baseline', 'active', 'api', 'full']},
        'target_url': {'type': 'string', 'format': 'uri'},
        'api_definition': {'type': 'string', 'format': 'uri'},
        'api_format': {'type': 'string', 'enum': ['openapi', 'soap', 'graphql']},
        'alpha_passive': {'type': 'boolean'},
        'safe_mode': {'type': 'boolean'},
        'debug': {'type': 'boolean'},
        'format': {'type': 'string', 'enum': ['json', 'html', 'xml', 'md']},
        'max_time': {'type': 'integer', 'minimum': 0},
        'min_level': {'type': 'string', 'enum': ['PASS', 'IGNORE', 'INFO', 'WARN', 'FAIL']}
    }
}
```

## Frontend Implementation Requirements

### JavaScript Components

**Required JavaScript Modules**:
```javascript
// Tool configuration management
class ToolConfigManager {
    constructor() {
        this.configurations = {};
        this.validators = {};
    }
    
    loadToolConfig(toolName) {
        // Load tool-specific configuration panel via HTMX
    }
    
    validateConfig(toolName, config) {
        // Real-time validation
    }
    
    saveConfiguration(toolName, config) {
        // Save configuration state
    }
}

// Result visualization
class ResultVisualization {
    constructor() {
        this.charts = {};
    }
    
    renderBanditResults(data) {
        // Create Bandit-specific visualizations
    }
    
    renderZapResults(data) {
        // Create ZAP-specific visualizations with Chart.js
    }
    
    renderPerformanceResults(data) {
        // Create performance charts and graphs
    }
}

// Export functionality
class ResultExporter {
    exportToPDF(testId) {
        // Generate PDF report
    }
    
    exportToJSON(testId) {
        // Export raw JSON data
    }
    
    exportToCSV(testId) {
        // Export tabular data to CSV
    }
}
```

### CSS/Styling Requirements

**Tool-Specific Styling**:
```css
/* Severity-based styling */
.severity-critical { border-left: 4px solid #dc3545; background-color: #f8d7da; }
.severity-high { border-left: 4px solid #fd7e14; background-color: #ffeaa7; }
.severity-medium { border-left: 4px solid #ffc107; background-color: #fff3cd; }
.severity-low { border-left: 4px solid #28a745; background-color: #d4edda; }

/* ZAP risk styling */
.risk-high { border: 2px solid #dc3545; }
.risk-medium { border: 2px solid #ffc107; }
.risk-low { border: 2px solid #28a745; }
.risk-info { border: 2px solid #17a2b8; }

/* Performance metrics */
.metric-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 10px;
    padding: 20px;
    color: white;
    text-align: center;
}

.metric-value {
    font-size: 2rem;
    font-weight: bold;
}

/* Code highlighting */
.code-block {
    background: #f8f9fa;
    border: 1px solid #e9ecef;
    border-radius: 6px;
    padding: 15px;
    margin: 10px 0;
}

.code-block pre {
    margin: 0;
    background: transparent;
    border: none;
}
```

## Integration Points

### Existing System Compatibility

**Maintain Compatibility With**:
1. Current database models (`BatchJob`, `ContainerizedTest`, etc.)
2. Existing API endpoints for backward compatibility
3. Service locator pattern (`ServiceLocator.get_*()`)
4. HTMX-based UI updates
5. Bootstrap 5 styling framework

### Service Communication

**Enhanced Service Integration**:
```python
# Extended service client with detailed configuration support
class EnhancedTestingClient:
    def submit_enhanced_security_test(self, config):
        """Submit security test with full configuration support."""
        request_data = {
            "model": config['model'],
            "app_num": config['app_number'],
            "test_type": "security_enhanced",
            "tools": config['tools'],
            "tool_configurations": config['tool_configs'],
            "timeout": config.get('timeout', 300)
        }
        
        response = requests.post(
            f"{self.services['security-scanner']}/tests/enhanced",
            json=request_data,
            timeout=30
        )
        
        return self._poll_enhanced_results(response.json()["test_id"])
    
    def get_detailed_results(self, test_id, tool_name=None):
        """Get detailed, tool-specific results."""
        if tool_name:
            endpoint = f"/tests/{test_id}/results/{tool_name}"
        else:
            endpoint = f"/tests/{test_id}/results/detailed"
            
        response = requests.get(f"{self.services['security-scanner']}{endpoint}")
        return response.json()
```

## Technical Considerations

### Performance Optimization

1. **Lazy Loading**: Load tool configuration panels on demand
2. **Result Streaming**: Stream large result sets via WebSocket
3. **Caching**: Cache tool configurations and frequent queries
4. **Pagination**: Implement pagination for large result sets

### Security Considerations

1. **Input Validation**: Comprehensive validation for all tool configurations
2. **File Upload Security**: Secure handling of policy/configuration files
3. **Output Sanitization**: Prevent XSS in displayed results
4. **Rate Limiting**: Protect against abuse of test creation endpoints

### Accessibility

1. **ARIA Labels**: Comprehensive accessibility markup
2. **Keyboard Navigation**: Full keyboard support for all interfaces
3. **Screen Reader Support**: Proper semantic markup
4. **Color Accessibility**: Color-blind friendly severity indicators

## Implementation Timeline

### Phase 1: Test Creation Page (Week 1-2)
- Create comprehensive test creation interface
- Implement tool-specific configuration panels
- Add real-time validation and preview

### Phase 2: Dashboard Enhancement (Week 2-3)
- Enhance existing dashboard with detailed service management
- Add comprehensive test history and filtering
- Implement advanced statistics and monitoring

### Phase 3: Results & Details Page (Week 3-4)
- Create detailed results display system
- Implement tool-specific result visualizations
- Add export and comparison functionality

### Phase 4: Integration & Testing (Week 4-5)
- Integrate all components
- Comprehensive testing across all tools
- Performance optimization and bug fixes

## Success Criteria

1. **Functionality**: All testing tools fully configurable through UI
2. **Usability**: Intuitive navigation and clear information hierarchy
3. **Performance**: Page load times under 2 seconds
4. **Reliability**: 99.9% uptime for critical testing operations
5. **Maintainability**: Clean, documented, and extensible codebase

## Resources and References

### Documentation Sources
- **OWASP ZAP**: https://www.zaproxy.org/docs/api/
- **Bandit**: https://bandit.readthedocs.io/en/latest/config.html
- **Safety**: https://pyup.io/docs/safety-cli/
- **Locust**: https://docs.locust.io/en/stable/
- **Semgrep**: https://semgrep.dev/docs/cli-reference/

### Existing Codebase References
- `src/unified_cli_analyzer.py` - Service orchestration patterns
- `testing-infrastructure/containers/` - Container service implementations
- `src/web_routes.py` - Current API endpoint patterns
- `src/models.py` - Database model definitions
- `tests/unit/test_analysis_comprehensive.py` - Testing patterns

This comprehensive implementation plan provides a roadmap for creating a sophisticated, professional-grade testing interface that will significantly enhance the usability and capability of the security testing platform.
