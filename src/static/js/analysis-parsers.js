/**
 * Analysis Parsers Module
 * Handles parsing and normalization of different analysis tool outputs.
 */

(function() {

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
            for (const [toolName, toolData] of Object.entries(tools)) {
                const issues = Array.isArray(toolData) ? toolData : (toolData.issues || []);
                issues.forEach((issue, index) => {
                    flattened.push({
                        id: `${toolName}-${index}`,
                        tool: toolName,
                        language: lang,
                        severity: this.normalizeSeverity(issue.severity || issue.level || issue.issue_severity),
                        message: issue.message || issue.text || issue.description || issue.issue_text,
                        file: issue.file || issue.path || issue.filename,
                        line: issue.line || issue.start_line || issue.line_number,
                        raw: issue
                    });
                });
            }
        }
        return flattened;
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
            raw: rawToolData
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
            
            // Parse requirements-checker results
            const reqChecker = toolsMap['requirements-checker'] || {};
            if (reqChecker.status === 'success' && reqChecker.results) {
                const reqResults = reqChecker.results;
                
                // Functional requirements
                if (reqResults.functional_requirements) {
                    reqResults.functional_requirements.forEach((req, idx) => {
                        flattened.push({
                            id: `ai-func-req-${idx}`,
                            tool: 'requirements-checker',
                            severity: req.met ? 'success' : 'high',
                            message: req.requirement,
                            status: req.met ? 'Met' : 'Not Met',
                            confidence: req.confidence,
                            category: 'functional',
                            raw: req
                        });
                    });
                }
                
                // Control endpoint tests
                if (reqResults.control_endpoint_tests) {
                    reqResults.control_endpoint_tests.forEach((test, idx) => {
                        flattened.push({
                            id: `ai-control-${idx}`,
                            tool: 'requirements-checker',
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
                
                // Stylistic requirements
                if (qualityResults.stylistic_requirements) {
                    qualityResults.stylistic_requirements.forEach((req, idx) => {
                        flattened.push({
                            id: `ai-style-req-${idx}`,
                            tool: 'code-quality-analyzer',
                            severity: req.met ? 'success' : 'medium',
                            message: req.requirement,
                            status: req.met ? 'Met' : 'Not Met',
                            confidence: req.confidence,
                            category: 'stylistic',
                            raw: req
                        });
                    });
                }
            }
            
            return flattened;
        }

        // Legacy single-tool format fallback
        const results = analysis.results || {};

        if (results.functional_requirements) {
            results.functional_requirements.forEach((req, idx) => {
                flattened.push({
                    id: `ai-req-${idx}`,
                    tool: 'requirements-checker',
                    severity: req.met ? 'success' : 'high',
                    message: req.requirement,
                    status: req.met ? 'Met' : 'Not Met',
                    confidence: req.confidence,
                    category: 'functional',
                    raw: req
                });
            });
        }
        
        if (results.stylistic_requirements) {
            results.stylistic_requirements.forEach((req, idx) => {
                flattened.push({
                    id: `ai-style-${idx}`,
                    tool: 'code-quality-analyzer',
                    severity: req.met ? 'success' : 'medium',
                    message: req.requirement,
                    status: req.met ? 'Met' : 'Not Met',
                    confidence: req.confidence,
                    category: 'stylistic',
                    raw: req
                });
            });
        }
        
        if (results.control_endpoint_tests) {
            results.control_endpoint_tests.forEach((test, idx) => {
                flattened.push({
                    id: `ai-control-${idx}`,
                    tool: 'requirements-checker',
                    severity: test.passed ? 'success' : 'high',
                    message: test.endpoint,
                    status: test.passed ? 'Passed' : 'Failed',
                    confidence: 'HIGH',
                    category: 'control',
                    raw: test
                });
            });
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
        // The structure is data.results.services[type]
        const serviceData = data?.results?.services?.[type] || {};

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
