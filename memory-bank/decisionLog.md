# Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-07-28 | Integrated comprehensive JavaScript frontend security and quality analysis tools via npx | The thesis research analyzes 900+ AI-generated applications with React frontends. By integrating retire.js, enhanced Snyk, JSHint, Prettier, and security-focused ESLint configurations, we can now detect JavaScript vulnerabilities, vulnerable dependencies, code quality issues, and formatting problems. Using npx ensures tools are available without complex installation requirements. Separate security vs quality analysis allows for targeted insights. This significantly enhances the frontend analysis capabilities needed for comprehensive AI application security research. |
| 2025-07-31 | CLI Tools Testing Method Names - The actual method calls in web_routes.py differ from service class methods | After examining web_routes.py, the actual method calls are:
- ScanManager.run_security_analysis() - for security analysis
- performance_service.run_performance_test() - for performance testing  
- zap_service.run_zap_scan() - for ZAP scanning

These methods are called through ServiceLocator.get_service() pattern, not direct class instantiation. The ScanManager in core_services.py manages scans but doesn't have run_security_analysis method - this explains the test failures. Need to understand actual service integration patterns. |
| 2025-08-02 | Resolved TemplateNotFound error by creating missing pages/batch_jobs_list.html template | The Flask application was failing with jinja2.exceptions.TemplateNotFound: pages/batch_jobs_list.html when accessing /batch/ route. Investigation revealed the template file was missing from src/templates/pages/. Created comprehensive batch jobs management template with proper Jinja2 structure, Bootstrap styling, HTMX integration, and error handling. Template now renders successfully with 24,439 characters and passes all 4 comprehensive test suites. |
