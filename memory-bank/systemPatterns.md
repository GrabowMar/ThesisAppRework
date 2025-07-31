# System Patterns

## Architectural Patterns

- Pattern 1: Description

## Design Patterns

- Pattern 1: Description

## Common Idioms

- Idiom 1: Description

## Frontend Security Analysis Tool Integration Pattern

Integrated JavaScript security and quality tools using npx-based detection and execution. Tools are categorized into security-focused (retire.js for vulnerable libraries, Snyk for dependencies, ESLint with security rules, JSHint for unsafe patterns) and quality-focused (Prettier for formatting, ESLint for code quality, JSHint for best practices). Each tool has custom output parsers that convert results into standardized AnalysisIssue objects with consistent severity, confidence, and categorization. Tool availability is checked via npx, and configuration is handled through temporary config files. Results are cached to avoid redundant analysis.

### Examples

- FrontendSecurityAnalyzer uses retire.js to detect CVE vulnerabilities in JavaScript libraries
- Snyk integration automatically installs npm dependencies before scanning
- ESLint security rules detect XSS and injection vulnerabilities
- Prettier integration checks code formatting consistency
- UnifiedCLIAnalyzer orchestrates all frontend tools with backend tools for comprehensive analysis


## CLI Tools Testing Architecture

The application uses separate service modules for different analysis types:

1. **Security Analysis Service (security_analysis_service.py)**:
   - UnifiedCLIAnalyzer class as main interface
   - Separate analyzers: BackendSecurityAnalyzer, FrontendSecurityAnalyzer, BackendQualityAnalyzer, FrontendQualityAnalyzer
   - Tools: bandit, safety, pylint, vulture (backend), npm audit, eslint, retire, jshint, snyk (frontend)
   - Uses ToolCategory enum and AnalysisIssue dataclass
   - Method: run_analysis(model, app_num, categories, use_all_tools, force_rerun)

2. **Performance Service (performance_service.py)**:
   - LocustPerformanceTester class for load testing
   - Uses Locust library with safe imports to avoid monkey-patching issues
   - Method: run_performance_test(model, app_num) 
   - Returns PerformanceResult with detailed stats

3. **ZAP Service (zap_service.py)**:
   - ZAPScanner class for security scanning
   - Uses OWASP ZAP for web application security testing
   - Method: scan_app(model, app_num) for batch analysis compatibility
   - ZAPDaemonManager for lifecycle management

4. **OpenRouter Service (openrouter_service.py)**:
   - OpenRouterAnalyzer for AI-based code analysis
   - Uses OpenRouter API to analyze code against requirements
   - Method: analyze_app(model, app_num)

All services follow consistent patterns with model/app_num parameters and result saving.

### Examples

- security_analysis_service.py: UnifiedCLIAnalyzer.run_analysis()
- performance_service.py: LocustPerformanceTester.run_performance_test()
- zap_service.py: ZAPScanner.scan_app()
- openrouter_service.py: OpenRouterAnalyzer.analyze_app()


## Service Integration Mismatch

The web routes use specific service access patterns and method calls that differ from the actual service class definitions:

**Performance Service Integration**:
- Access: `ServiceLocator.get_service('performance_service')`
- Method: `performance_service.run_performance_test(model, app_num)`
- Note: This service is registered separately, not through core_services.py

**ZAP Service Integration**:
- Access: `ServiceLocator.get_service('zap_service')`
- Method: `zap_service.run_zap_scan(model, app_num, scan_type)`
- Note: This service is registered separately, not through core_services.py

**Security Analysis Integration**:
- Access: `ServiceLocator.get_scan_manager()` (from core_services.py)
- Method: `scan_service.run_security_analysis(model, app_num, enabled_tools)`
- Issue: ScanManager in core_services.py doesn't have run_security_analysis method

**Service Registration Gap**:
The issue is that performance_service and zap_service are accessed as separate services, but may not be properly registered in the ServiceLocator. The ScanManager from core_services.py is used but lacks the expected run_security_analysis method.

### Examples

- ServiceLocator.get_service('performance_service')
- ServiceLocator.get_service('zap_service')
- ServiceLocator.get_scan_manager()
- performance_service.run_performance_test()
- zap_service.run_zap_scan()
- scan_service.run_security_analysis()
