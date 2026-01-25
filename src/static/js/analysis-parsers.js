/**
 * Analysis Parsers Module
 * Handles parsing and normalization of different analysis tool outputs.
 */

(function () {

    class BaseParser {
        constructor(data) {
            this.data = data;
        }

        /**
         * Parse the raw data into a standardized format.
         * @returns {Object} Standardized result object
         */
        parse() {
            throw new Error('parse() must be implemented by subclass');
        }

        /**
         * Get standardized data for a specific tool.
         * @param {string} toolName Name of the tool
         * @returns {Object} Standardized tool data { summary, issues, metrics, sarif_file }
         */
        getToolData(toolName) {
            throw new Error('getToolData() must be implemented by subclass');
        }

        /**
         * Helper to determine severity level
         * @param {string} severity Raw severity string
         * @returns {string} Normalized severity (critical, high, medium, low, info)
         */
        normalizeSeverity(severity) {
            if (!severity) return 'info';
            const s = String(severity).toLowerCase();
            if (s.includes('critical')) return 'critical';
            if (s.includes('high') || s.includes('error')) return 'high';
            if (s.includes('medium') || s.includes('warn')) return 'medium';
            if (s.includes('low') || s.includes('note')) return 'low';
            return 'info';
        }
    }

    class SarifParser {
        static parse(sarifData) {
            const issues = [];
            if (!sarifData || !sarifData.runs) return issues;

            sarifData.runs.forEach(run => {
                const toolName = run.tool?.driver?.name || 'Unknown Tool';
                const rules = run.tool?.driver?.rules || [];
                const rulesMap = new Map(rules.map(r => [r.id, r]));

                (run.results || []).forEach((result, idx) => {
                    const rule = rulesMap.get(result.ruleId);
                    const severity = SarifParser.normalizeSarifLevel(result.level || rule?.defaultConfiguration?.level);

                    const location = result.locations?.[0]?.physicalLocation;
                    const file = location?.artifactLocation?.uri || 'unknown';
                    const line = location?.region?.startLine || 0;

                    issues.push({
                        id: `sarif-${toolName}-${idx}`,
                        tool: toolName,
                        severity: severity,
                        message: result.message?.text || rule?.shortDescription?.text || 'No description',
                        file: file,
                        line: line,
                        raw: result,
                        ruleId: result.ruleId
                    });
                });
            });
            return issues;
        }

        static normalizeSarifLevel(level) {
            if (!level) return 'info';
            switch (level.toLowerCase()) {
                case 'error': return 'high';
                case 'warning': return 'medium';
                case 'note': return 'low';
                default: return 'info';
            }
        }
    }

    class StaticParser extends BaseParser {
        parse() {
            const flattened = [];
            const results = this.data.analysis?.results || {};

            for (const [lang, tools] of Object.entries(results)) {
                // Skip structure/metadata keys
                if (lang === 'structure' || lang === '_metadata') continue;

                for (const [toolName, toolData] of Object.entries(tools)) {
                    // Skip metadata keys
                    if (['tool_status', '_metadata', 'status', 'message', 'error'].includes(toolName)) continue;

                    // Extract issues based on tool type
                    let issues = this.extractToolIssues(toolName, toolData);

                    // If no issues extracted, try common patterns
                    if (issues.length === 0) {
                        issues = Array.isArray(toolData) ? toolData : (toolData.issues || []);
                    }

                    // If issues array is empty but SARIF data exists, extract from SARIF
                    if (issues.length === 0 && toolData.sarif && toolData.sarif.runs) {
                        issues = SarifParser.parse(toolData.sarif);
                        issues = issues.map(issue => ({ ...issue, language: lang }));
                    }

                    issues.forEach((issue, index) => {
                        flattened.push({
                            id: `${toolName}-${index}`,
                            tool: toolName,
                            language: issue.language || lang,
                            severity: this.normalizeSeverity(issue.severity || issue.level || issue.issue_severity || issue.type),
                            message: issue.message || issue.text || issue.description || issue.issue_text,
                            file: (issue.file || issue.path || issue.filename || '').replace('/app/sources/', ''),
                            line: issue.line || issue.start_line || issue.line_number || issue.lineno,
                            raw: issue
                        });
                    });
                }
            }
            return flattened;
        }

        /**
         * Extract issues from specific tool formats
         */
        extractToolIssues(toolName, toolData) {
            const issues = [];
            const t = toolName.toLowerCase();

            // Bandit - Python security scanner
            if (t === 'bandit') {
                (toolData.issues || []).forEach(issue => {
                    issues.push({
                        severity: issue.issue_severity,
                        message: issue.issue_text,
                        file: issue.filename,
                        line: issue.line_number,
                        rule_id: issue.test_id,
                        raw: issue
                    });
                });
            }
            // Ruff - Fast Python linter
            else if (t === 'ruff') {
                (toolData.issues || []).forEach(issue => {
                    issues.push({
                        severity: issue.type || 'warning',
                        message: issue.message,
                        file: issue.filename || issue.file,
                        line: issue.line || issue.location?.row,
                        rule_id: issue.code || issue.rule,
                        raw: issue
                    });
                });
            }
            // Pylint
            else if (t === 'pylint') {
                (toolData.issues || []).forEach(issue => {
                    issues.push({
                        severity: issue.type,
                        message: issue.message,
                        file: issue.path,
                        line: issue.line,
                        rule_id: issue['message-id'] || issue.symbol,
                        raw: issue
                    });
                });
            }
            // MyPy - Python type checker
            else if (t === 'mypy') {
                (toolData.issues || []).forEach(issue => {
                    issues.push({
                        severity: issue.severity || 'error',
                        message: issue.message,
                        file: issue.file,
                        line: issue.line,
                        rule_id: issue.code || 'type-error',
                        raw: issue
                    });
                });
            }
            // Vulture - Dead code detector
            else if (t === 'vulture') {
                (toolData.issues || []).forEach(issue => {
                    issues.push({
                        severity: 'low',
                        message: issue.message || `Unused ${issue.typ}: ${issue.name}`,
                        file: issue.filename || issue.file,
                        line: issue.first_lineno || issue.line,
                        rule_id: 'unused-code',
                        raw: issue
                    });
                });
            }
            // Radon - Complexity analyzer
            else if (t === 'radon') {
                const complexity = toolData.complexity || toolData.raw || {};
                if (typeof complexity === 'object') {
                    Object.entries(complexity).forEach(([filePath, functions]) => {
                        if (Array.isArray(functions)) {
                            functions.forEach(func => {
                                const rank = func.rank || 'A';
                                if (['C', 'D', 'E', 'F'].includes(rank)) {
                                    issues.push({
                                        severity: rank === 'F' || rank === 'E' ? 'high' : rank === 'D' ? 'medium' : 'low',
                                        message: `Function '${func.name}' has complexity ${func.complexity} (rank ${rank})`,
                                        file: filePath,
                                        line: func.lineno,
                                        rule_id: `complexity-${rank}`,
                                        raw: func
                                    });
                                }
                            });
                        }
                    });
                }
            }
            // Safety - Python vulnerability scanner
            else if (t === 'safety') {
                (toolData.vulnerabilities || toolData.issues || []).forEach(vuln => {
                    issues.push({
                        severity: vuln.severity || 'medium',
                        message: `Vulnerable package: ${vuln.package_name || vuln.package} ${vuln.vulnerable_versions || ''}`,
                        file: 'requirements.txt',
                        line: '-',
                        rule_id: vuln.vulnerability_id || vuln.id || vuln.CVE,
                        raw: vuln
                    });
                });
            }
            // Pip-audit
            else if (t === 'pip-audit' || t === 'pip_audit') {
                (toolData.vulnerabilities || toolData.issues || []).forEach(vuln => {
                    issues.push({
                        severity: vuln.severity || 'medium',
                        message: `Vulnerable: ${vuln.name || vuln.package} ${vuln.version || ''}`,
                        file: 'requirements.txt',
                        line: '-',
                        rule_id: vuln.id || vuln.vulnerability_id,
                        raw: vuln
                    });
                });
            }
            // Detect-secrets
            else if (t === 'detect-secrets' || t === 'detect_secrets') {
                const secrets = toolData.results || toolData.issues || {};
                if (typeof secrets === 'object' && !Array.isArray(secrets)) {
                    Object.entries(secrets).forEach(([filePath, fileSecrets]) => {
                        if (Array.isArray(fileSecrets)) {
                            fileSecrets.forEach(secret => {
                                issues.push({
                                    severity: 'high',
                                    message: `Potential ${secret.type || 'secret'} detected`,
                                    file: filePath,
                                    line: secret.line_number,
                                    rule_id: secret.type || 'secret-detected',
                                    raw: secret
                                });
                            });
                        }
                    });
                } else if (Array.isArray(secrets)) {
                    secrets.forEach((secret) => {
                        issues.push({
                            severity: secret.severity || 'high',
                            message: secret.message || `Potential ${secret.type || 'secret'} detected`,
                            file: secret.filename || secret.file,
                            line: secret.line_number || secret.line,
                            rule_id: secret.rule || secret.type || 'secret-detected',
                            raw: secret
                        });
                    });
                }
            }
            // ESLint
            else if (t === 'eslint') {
                (toolData.results || []).forEach(fileResult => {
                    (fileResult.messages || []).forEach(msg => {
                        issues.push({
                            severity: msg.severity === 2 ? 'high' : 'medium',
                            message: msg.message,
                            file: fileResult.filePath,
                            line: msg.line,
                            rule_id: msg.ruleId,
                            raw: msg
                        });
                    });
                });
            }
            // Stylelint
            else if (t === 'stylelint') {
                (toolData.results || []).forEach(fileResult => {
                    (fileResult.warnings || []).forEach(warn => {
                        issues.push({
                            severity: warn.severity || 'warning',
                            message: warn.text,
                            file: fileResult.source,
                            line: warn.line,
                            rule_id: warn.rule,
                            raw: warn
                        });
                    });
                });
            }
            // NPM-audit
            else if (t === 'npm-audit' || t === 'npm_audit') {
                const advisories = toolData.advisories || toolData.vulnerabilities || toolData.issues || {};
                if (typeof advisories === 'object' && !Array.isArray(advisories)) {
                    Object.entries(advisories).forEach(([advId, advisory]) => {
                        issues.push({
                            severity: advisory.severity || 'moderate',
                            message: `Vulnerable: ${advisory.module_name || ''} - ${advisory.title || advisory.overview || ''}`,
                            file: 'package.json',
                            line: '-',
                            rule_id: advId,
                            raw: advisory
                        });
                    });
                } else if (Array.isArray(advisories)) {
                    advisories.forEach(advisory => {
                        issues.push({
                            severity: advisory.severity || 'moderate',
                            message: `Vulnerable: ${advisory.name || advisory.module_name || ''} - ${advisory.title || ''}`,
                            file: 'package.json',
                            line: '-',
                            rule_id: advisory.id,
                            raw: advisory
                        });
                    });
                }
            }
            // Semgrep
            else if (t === 'semgrep') {
                (toolData.results || []).forEach(res => {
                    const extra = res.extra || {};
                    issues.push({
                        severity: extra.severity || 'warning',
                        message: extra.message || res.check_id,
                        file: res.path,
                        line: res.start?.line,
                        rule_id: res.check_id,
                        raw: res
                    });
                });
            }

            return issues;
        }

        getToolData(toolName) {
            const allFindings = this.parse();
            const toolFindings = allFindings.filter(i => i.tool === toolName);

            // Find raw tool data for summary and metadata
            let rawToolData = {};
            const results = this.data.analysis?.results || {};
            for (const [lang, tools] of Object.entries(results)) {
                if (tools[toolName]) {
                    rawToolData = tools[toolName];
                    rawToolData._language = lang;
                    break;
                }
            }

            // Check for SARIF file reference
            const sarifFile = rawToolData.sarif?.sarif_file || rawToolData.sarif_file;

            return {
                summary: {
                    name: toolName,
                    status: rawToolData.status || 'unknown',
                    total_issues: rawToolData.total_issues || rawToolData.issue_count || toolFindings.length,
                    execution_time: rawToolData.execution_record?.duration || rawToolData.duration
                },
                issues: toolFindings,
                metrics: [],
                sarif_file: sarifFile,
                raw: rawToolData  // Include full raw data
            };
        }

        getDetail(id) {
            const item = this.parse().find(i => i.id === id);
            if (!item) return null;

            return {
                title: item.message,
                subtitle: `${item.tool} (${item.language || 'Static Analysis'})`,
                severity: item.severity,
                description: item.raw.description || item.message,
                location: `${item.file}:${item.line}`,
                code: item.raw.code || item.raw.context || null,
                remediation: item.raw.remediation || item.raw.solution || null,
                evidence: item.raw
            };
        }
    }

    class DynamicParser extends BaseParser {
        parse() {
            const results = this.data.analysis?.results || {};
            const flattened = [];

            // Handle ZAP
            if (results.zap_security_scan) {
                results.zap_security_scan.forEach((scan, scanIdx) => {
                    const alerts = scan.alerts_by_risk || {};
                    Object.entries(alerts).forEach(([risk, items]) => {
                        items.forEach((item, itemIdx) => {
                            flattened.push({
                                id: `zap-${scanIdx}-${risk}-${itemIdx}`,
                                tool: 'zap',
                                type: 'security_scan',
                                severity: this.normalizeSeverity(risk),
                                message: item.alert || item.name,
                                url: item.url,
                                raw: item
                            });
                        });
                    });
                });
            }

            // Handle Vulnerability Scan
            if (results.vulnerability_scan) {
                results.vulnerability_scan.forEach((scan, scanIdx) => {
                    (scan.vulnerabilities || []).forEach((vuln, vulnIdx) => {
                        flattened.push({
                            id: `vuln-${scanIdx}-${vulnIdx}`,
                            tool: 'vulnerability_scan',
                            type: 'vulnerability',
                            severity: this.normalizeSeverity(vuln.severity),
                            message: vuln.description || vuln.type,
                            url: scan.url,
                            raw: vuln
                        });
                    });
                });
            }

            // Handle Nmap (Port Scan)
            if (results.port_scan) {
                const ps = results.port_scan;
                // Handle both array of ports and object with open_ports
                const openPorts = Array.isArray(ps) ? ps : (ps.open_ports || []);

                openPorts.forEach((port, idx) => {
                    flattened.push({
                        id: `nmap-${idx}`,
                        tool: 'nmap',
                        type: 'port_scan',
                        severity: 'info',
                        message: `Open Port: ${port}`,
                        url: ps.host || 'target',
                        raw: { port: port, ...ps }
                    });
                });
            }

            return flattened;
        }

        getToolData(toolName) {
            const allFindings = this.parse();
            // Normalize tool name matching
            const toolFindings = allFindings.filter(i => i.tool === toolName || (toolName === 'vulnscan' && i.tool === 'vulnerability_scan'));

            // Find raw data for status
            let status = 'completed';
            const results = this.data.analysis?.results || {};
            if (toolName === 'zap' && results.zap_security_scan) status = 'success';
            if (toolName === 'nmap' && results.port_scan) status = 'success';

            return {
                summary: {
                    name: toolName,
                    status: status,
                    total_issues: toolFindings.length
                },
                issues: toolFindings,
                metrics: []
            };
        }

        getDetail(id) {
            const item = this.parse().find(i => i.id === id);
            if (!item) return null;

            return {
                title: item.message,
                subtitle: `${item.tool} - ${item.type}`,
                severity: item.severity,
                description: item.raw.description || item.raw.other || item.message,
                location: item.url,
                code: item.raw.evidence || null,
                remediation: item.raw.solution || null,
                evidence: item.raw
            };
        }
    }

    class PerformanceParser extends BaseParser {
        parse() {
            const results = this.data.analysis?.results || {};
            const flattened = [];

            // Handle tool_runs if present (normalized format)
            const toolRuns = results.tool_runs || {};

            // Also check for direct tool keys if tool_runs is missing
            const toolsToCheck = Object.keys(results).filter(k => !['tool_runs', 'summary', 'status'].includes(k));

            // Merge sources
            const allTools = { ...toolRuns };
            toolsToCheck.forEach(k => {
                if (!allTools[k] && typeof results[k] === 'object') {
                    allTools[k] = results[k];
                }
            });

            Object.entries(allTools).forEach(([key, toolData]) => {
                // Skip metadata
                if (['summary', 'status', 'error'].includes(key)) return;

                const toolName = toolData.tool || key;
                const url = toolData.url || 'unknown';

                if (toolData.status === 'failed' || toolData.status === 'error') {
                    flattened.push({
                        id: `perf-${key}-error`,
                        tool: toolName,
                        url: url,
                        severity: 'high',
                        message: `Tool execution failed: ${toolData.error || 'Unknown error'}`,
                        metric: 'Execution Status',
                        value: 'Failed',
                        raw: toolData
                    });
                } else {
                    // Extract metrics
                    const metrics = toolData.metrics || toolData;

                    if (metrics.requests_per_second !== undefined) {
                        flattened.push({
                            id: `perf-${key}-rps`,
                            tool: toolName,
                            url: url,
                            severity: 'info',
                            message: `RPS: ${Number(metrics.requests_per_second).toFixed(2)}`,
                            metric: 'Requests/Sec',
                            value: metrics.requests_per_second,
                            raw: toolData
                        });
                    }
                    if (metrics.avg_response_time !== undefined) {
                        flattened.push({
                            id: `perf-${key}-latency`,
                            tool: toolName,
                            url: url,
                            severity: metrics.avg_response_time > 1000 ? 'medium' : 'info',
                            message: `Avg Latency: ${Number(metrics.avg_response_time).toFixed(2)}ms`,
                            metric: 'Latency',
                            value: metrics.avg_response_time,
                            raw: toolData
                        });
                    }
                }
            });

            return flattened;
        }

        getToolData(toolName) {
            const allFindings = this.parse();
            const toolFindings = allFindings.filter(i => i.tool === toolName);

            // Extract metrics for the summary
            const metrics = toolFindings.map(f => ({
                name: `${f.metric} (${f.url})`,
                value: typeof f.value === 'number' ? f.value.toFixed(2) : f.value
            }));

            return {
                summary: {
                    name: toolName,
                    status: 'completed',
                    total_issues: toolFindings.filter(f => f.severity === 'high').length
                },
                issues: toolFindings,
                metrics: metrics
            };
        }

        getDetail(id) {
            const item = this.parse().find(i => i.id === id);
            if (!item) return null;

            return {
                title: item.message,
                subtitle: `${item.tool} - ${item.url}`,
                severity: item.severity,
                description: `Performance metric for ${item.url}`,
                location: item.url,
                code: JSON.stringify(item.raw.configuration || {}, null, 2),
                remediation: null,
                evidence: item.raw
            };
        }
    }

    class AiParser extends BaseParser {
        parse() {
            const analysis = this.data.analysis || {};
            const flattened = [];

            // Check for new multi-tool format first
            const toolsMap = analysis.tools || {};
            if (Object.keys(toolsMap).length > 0) {
                // New multi-tool format

                // Parse requirements-scanner results
                const reqScanner = toolsMap['requirements-scanner'] || {};
                if (reqScanner.status === 'success' && reqScanner.results) {
                    const reqResults = reqScanner.results;

                    // Backend requirements (new format)
                    const backendReqs = reqResults.backend_requirements || [];
                    backendReqs.forEach((req, idx) => {
                        flattened.push({
                            id: `ai-backend-req-${idx}`,
                            tool: 'requirements-scanner',
                            severity: req.met ? 'success' : 'high',
                            message: req.requirement,
                            status: req.met ? 'Met' : 'Not Met',
                            confidence: req.confidence,
                            category: 'backend',
                            raw: req
                        });
                    });

                    // Frontend requirements (new format)
                    if (reqResults.frontend_requirements) {
                        reqResults.frontend_requirements.forEach((req, idx) => {
                            flattened.push({
                                id: `ai-frontend-req-${idx}`,
                                tool: 'requirements-scanner',
                                severity: req.met ? 'success' : 'high',
                                message: req.requirement,
                                status: req.met ? 'Met' : 'Not Met',
                                confidence: req.confidence,
                                category: 'frontend',
                                raw: req
                            });
                        });
                    }

                    // Admin requirements (new format)
                    if (reqResults.admin_requirements) {
                        reqResults.admin_requirements.forEach((req, idx) => {
                            flattened.push({
                                id: `ai-admin-req-${idx}`,
                                tool: 'requirements-scanner',
                                severity: req.met ? 'success' : 'high',
                                message: req.requirement,
                                status: req.met ? 'Met' : 'Not Met',
                                confidence: req.confidence,
                                category: 'admin',
                                raw: req
                            });
                        });
                    }

                    // Control endpoint tests
                    if (reqResults.control_endpoint_tests) {
                        reqResults.control_endpoint_tests.forEach((test, idx) => {
                            flattened.push({
                                id: `ai-control-${idx}`,
                                tool: 'requirements-scanner',
                                severity: test.passed ? 'success' : 'high',
                                message: `${test.method || 'GET'} ${test.endpoint}`,
                                status: test.passed ? 'Passed' : 'Failed',
                                confidence: 'HIGH',
                                category: 'control',
                                raw: test
                            });
                        });
                    }
                }

                // Parse code-quality-analyzer results
                const qualityAnalyzer = toolsMap['code-quality-analyzer'] || {};
                if (qualityAnalyzer.status === 'success' && qualityAnalyzer.results) {
                    const qualityResults = qualityAnalyzer.results;

                    // New format: quality_metrics with scores
                    if (qualityResults.quality_metrics && qualityResults.quality_metrics.length > 0) {
                        qualityResults.quality_metrics.forEach((metric, idx) => {
                            flattened.push({
                                id: `ai-quality-metric-${idx}`,
                                tool: 'code-quality-analyzer',
                                severity: metric.passed ? 'success' : (metric.score < 40 ? 'high' : 'medium'),
                                message: metric.metric_name,
                                status: metric.passed ? 'Passed' : `Score: ${metric.score}/100`,
                                confidence: metric.confidence,
                                category: 'quality_metric',
                                score: metric.score,
                                findings: metric.findings || [],
                                recommendations: metric.recommendations || [],
                                raw: metric
                            });
                        });
                    }
                }

                return flattened;
            }
            return flattened;
        }

        getToolData(toolName) {
            const allFindings = this.parse();
            const toolFindings = toolName ? allFindings.filter(f => f.tool === toolName) : allFindings;

            return {
                summary: {
                    name: toolName || 'AI Requirements',
                    status: 'completed',
                    total_issues: toolFindings.filter(f => f.severity !== 'success').length
                },
                issues: toolFindings,
                metrics: []
            };
        }

        getDetail(id) {
            const item = this.parse().find(i => i.id === id);
            if (!item) return null;

            return {
                title: item.message,
                subtitle: `AI ${item.category ? item.category.charAt(0).toUpperCase() + item.category.slice(1) : 'Requirement'} Check (${item.confidence} Confidence)`,
                severity: item.severity === 'success' ? 'info' : item.severity,
                description: item.raw.explanation || item.raw.description || item.raw.error || 'No explanation provided.',
                location: 'N/A',
                code: null,
                remediation: item.raw.met ? null : 'Implement the missing requirement.',
                evidence: item.raw
            };
        }
    }

    // Factory to get the correct parser
    const AnalysisParserFactory = {
        getParser: (type, data) => {
            // Extract the specific service data if available
            // We expect data to be the full payload (window.ANALYSIS_DATA)
            // Support both nested (data.results.services) and flat (data.services) structures
            // Also support service name variants (static vs static-analyzer)
            const SERVICE_NAME_VARIANTS = {
                'static': ['static', 'static-analyzer'],
                'dynamic': ['dynamic', 'dynamic-analyzer'],
                'performance': ['performance', 'performance-tester'],
                'ai': ['ai', 'ai-analyzer']
            };

            // Try nested structure first, then flat structure
            let services = data?.results?.services || {};
            if (!services || Object.keys(services).length === 0) {
                services = data?.services || {};
            }

            // Find service data using variant names
            let serviceData = {};
            const variants = SERVICE_NAME_VARIANTS[type] || [type];
            for (const variant of variants) {
                if (services[variant]) {
                    serviceData = services[variant];
                    break;
                }
            }

            // Support both 'analysis' and 'payload' keys within service data
            if (!serviceData.analysis && serviceData.payload) {
                serviceData = { analysis: serviceData.payload, ...serviceData };
            }

            switch (type) {
                case 'static': return new StaticParser(serviceData);
                case 'dynamic': return new DynamicParser(serviceData);
                case 'performance': return new PerformanceParser(serviceData);
                case 'ai': return new AiParser(serviceData);
                default: return new BaseParser(serviceData);
            }
        },
        // Expose SarifParser for direct use
        SarifParser: SarifParser
    };

    // Export for use in browser
    window.AnalysisParserFactory = AnalysisParserFactory;

})();
