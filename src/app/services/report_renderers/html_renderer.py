"""
HTML Report Renderer

Generates self-contained HTML reports with embedded CSS (no Flask templates).
"""
import logging
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


def render_html(report, data: Dict[str, Any], output_path: Path) -> None:
    """
    Render report as self-contained HTML file.
    
    Args:
        report: Report model instance
        data: Report data dictionary
        output_path: Path where HTML file should be saved
    """
    try:
        # Route to appropriate renderer
        if report.report_type == 'app_analysis':
            html_content = _render_app_analysis_html(report, data)
        elif report.report_type == 'model_comparison':
            html_content = _render_model_comparison_html(report, data)
        elif report.report_type == 'tool_effectiveness':
            html_content = _render_tool_effectiveness_html(report, data)
        elif report.report_type == 'executive_summary':
            html_content = _render_executive_summary_html(report, data)
        else:
            html_content = _render_default_html(report, data)
        
        # Write to file
        output_path.write_text(html_content, encoding='utf-8')
        
        logger.info(f"Rendered HTML report to {output_path}")
        
    except Exception as e:
        logger.error(f"Error rendering HTML report: {e}", exc_info=True)
        raise


def _get_base_css() -> str:
    """Get embedded CSS for all reports - academic/scientific style."""
    return """
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        @import url('https://fonts.googleapis.com/css2?family=Crimson+Text:ital,wght@0,400;0,600;0,700;1,400&family=Source+Code+Pro:wght@400;600&display=swap');
        
        body { 
            font-family: 'Crimson Text', 'Georgia', 'Times New Roman', serif;
            font-size: 12pt;
            line-height: 1.8;
            color: #1a1a1a;
            background: white;
            padding: 0;
            max-width: 210mm; /* A4 width */
            margin: 0 auto;
        }
        
        .container { 
            padding: 25mm 20mm; /* A4 margins */
            background: white;
        }
        
        /* Academic Title */
        h1 { 
            font-family: 'Crimson Text', serif;
            font-size: 20pt;
            font-weight: 700;
            color: #000;
            text-align: center;
            margin: 0 0 8pt 0;
            text-transform: uppercase;
            letter-spacing: 0.5pt;
            border: none;
        }
        
        .subtitle {
            font-size: 14pt;
            font-style: italic;
            text-align: center;
            color: #333;
            margin-bottom: 20pt;
        }
        
        /* Section Headers */
        h2 { 
            font-family: 'Crimson Text', serif;
            font-size: 14pt;
            font-weight: 700;
            color: #000;
            margin: 20pt 0 10pt 0;
            border: none;
            padding: 0;
            counter-increment: section;
        }
        
        h2::before {
            content: counter(section) ". ";
            font-weight: 700;
        }
        
        h3 { 
            font-family: 'Crimson Text', serif;
            font-size: 12pt;
            font-weight: 600;
            font-style: italic;
            color: #000;
            margin: 15pt 0 8pt 0;
            counter-increment: subsection;
        }
        
        h3::before {
            content: counter(section) "." counter(subsection) " ";
        }
        
        /* Reset counters at document start */
        .container {
            counter-reset: section;
        }
        
        h2 {
            counter-reset: subsection;
        }
        
        /* Paragraph styling */
        p {
            text-align: justify;
            margin-bottom: 10pt;
            text-indent: 0;
            hyphens: auto;
        }
        
        /* Abstract box */
        .abstract {
            margin: 15pt 30pt;
            padding: 15pt;
            border: 1pt solid #666;
            background: #f9f9f9;
            font-size: 11pt;
        }
        
        .abstract-title {
            font-weight: 700;
            text-align: center;
            margin-bottom: 8pt;
            font-size: 11pt;
            text-transform: uppercase;
            letter-spacing: 1pt;
        }
        
        /* Metadata - Academic paper style */
        .metadata { 
            border: 1pt solid #999;
            padding: 10pt;
            margin: 15pt 0;
            background: #fafafa;
            font-size: 10pt;
            display: table;
            width: 100%;
        }
        
        .metadata-item {
            display: table-row;
        }
        
        .metadata-label { 
            display: table-cell;
            font-weight: 600;
            color: #000;
            padding: 3pt 10pt 3pt 0;
            white-space: nowrap;
            font-variant: small-caps;
        }
        
        .metadata-value { 
            display: table-cell;
            color: #333;
            padding: 3pt 0;
            font-family: 'Source Code Pro', 'Courier New', monospace;
            font-size: 9pt;
        }
        
        /* Tables - IEEE style */
        table { 
            width: 100%; 
            border-collapse: collapse; 
            margin: 15pt auto;
            font-size: 10pt;
            border-top: 2pt solid #000;
            border-bottom: 2pt solid #000;
        }
        
        caption {
            font-weight: 600;
            margin: 8pt 0;
            text-align: left;
            font-size: 10pt;
            caption-side: top;
        }
        
        th { 
            background: white;
            color: #000; 
            padding: 6pt 8pt;
            text-align: left;
            font-weight: 600;
            border-bottom: 1pt solid #000;
            font-variant: small-caps;
        }
        
        td { 
            padding: 5pt 8pt;
            border-bottom: 0.5pt solid #ddd;
            vertical-align: top;
        }
        
        tr:last-child td {
            border-bottom: none;
        }
        
        /* Code and mathematical notation */
        code, .math {
            font-family: 'Source Code Pro', 'Courier New', monospace;
            font-size: 10pt;
            background: #f5f5f5;
            padding: 1pt 3pt;
            border: 0.5pt solid #ddd;
        }
        
        .equation {
            font-family: 'STIX Two Text', 'Cambria Math', serif;
            font-style: italic;
            text-align: center;
            margin: 10pt 0;
            padding: 8pt;
            background: #fafafa;
        }
        
        /* Severity indicators - subtle academic style */
        .severity-critical { 
            font-weight: 600;
            color: #8B0000;
            font-variant: small-caps;
        }
        .severity-high { 
            font-weight: 600;
            color: #CD5C5C;
            font-variant: small-caps;
        }
        .severity-medium { 
            font-weight: 600;
            color: #B8860B;
            font-variant: small-caps;
        }
        .severity-low { 
            font-weight: 600;
            color: #2F4F4F;
            font-variant: small-caps;
        }
        
        /* Statistics table */
        .stats-table {
            margin: 15pt 0;
            width: 100%;
        }
        
        .stat-row {
            display: flex;
            justify-content: space-between;
            padding: 5pt 0;
            border-bottom: 0.5pt solid #ddd;
        }
        
        .stat-label {
            font-weight: 600;
            font-variant: small-caps;
        }
        
        .stat-value {
            font-family: 'Source Code Pro', monospace;
            font-weight: 600;
        }
        
        /* Findings enumeration */
        .findings-list {
            counter-reset: finding;
            list-style: none;
            margin: 10pt 0;
        }
        
        .finding-item {
            counter-increment: finding;
            margin: 10pt 0;
            padding: 8pt 10pt 8pt 30pt;
            border-left: 2pt solid #999;
            position: relative;
            background: #fafafa;
            page-break-inside: avoid;
        }
        
        .finding-item::before {
            content: "[" counter(finding) "]";
            position: absolute;
            left: 8pt;
            font-weight: 600;
            font-family: 'Source Code Pro', monospace;
            font-size: 9pt;
        }
        
        .finding-item.critical {
            border-left-color: #8B0000;
            background: #FFF5F5;
        }
        
        .finding-item.high {
            border-left-color: #CD5C5C;
            background: #FFF8F8;
        }
        
        .finding-item.medium {
            border-left-color: #B8860B;
            background: #FFFDF0;
        }
        
        .finding-item.low {
            border-left-color: #2F4F4F;
            background: #F8FAFA;
        }
        
        .finding-title {
            font-weight: 600;
            margin-bottom: 4pt;
        }
        
        .finding-desc {
            font-size: 10pt;
            color: #333;
            line-height: 1.6;
        }
        
        .finding-location {
            font-size: 9pt;
            font-family: 'Source Code Pro', monospace;
            color: #666;
            margin-top: 4pt;
        }
        
        /* References and citations */
        .reference {
            font-size: 10pt;
            margin: 5pt 0 5pt 15pt;
            text-indent: -15pt;
        }
        
        /* Footer - academic style */
        footer {
            margin-top: 30pt;
            padding-top: 10pt;
            border-top: 1pt solid #999;
            font-size: 9pt;
            color: #666;
            text-align: center;
        }
        
        .citation {
            font-style: italic;
            margin-top: 5pt;
        }
        
        /* Figure captions */
        .figure {
            margin: 15pt 0;
            text-align: center;
            page-break-inside: avoid;
        }
        
        .figure-caption {
            font-size: 10pt;
            margin-top: 8pt;
            font-style: italic;
            text-align: center;
        }
        
        /* Page break control */
        h2, h3 {
            page-break-after: avoid;
        }
        
        table, .finding-item, .figure {
            page-break-inside: avoid;
        }
        
        /* Print optimizations */
        @media print {
            body { 
                background: white;
                margin: 0;
            }
            .container {
                padding: 15mm;
            }
            a {
                color: #000;
                text-decoration: none;
            }
            /* Ensure black and white printing */
            * {
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
            }
        }
        
        /* Supplementary notation */
        .notation {
            font-size: 10pt;
            margin: 10pt 20pt;
            padding: 8pt;
            background: #f9f9f9;
            border-left: 2pt solid #666;
        }
        
        .notation-title {
            font-weight: 600;
            font-variant: small-caps;
            margin-bottom: 5pt;
        }
    </style>
    """


def _render_app_analysis_html(report, data: Dict[str, Any]) -> str:
    """Render app analysis report as HTML - academic style."""
    model = data.get('model_slug', 'Unknown')
    app_num = data.get('app_number', 'N/A')
    timestamp = data.get('timestamp', datetime.now().isoformat())
    
    findings = data.get('findings', [])
    tools = data.get('tools', {})
    summary = data.get('summary', {})
    
    # Count findings by severity
    severity_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
    for finding in findings:
        sev = finding.get('severity', 'low').lower()
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
    
    total_findings = len(findings)
    tools_count = len(tools)
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report.title}</title>
    {_get_base_css()}
</head>
<body>
    <div class="container">
        <h1>Automated Code Analysis Report:<br/>Application Generated by {model}</h1>
        
        <div class="subtitle">
            Static and Dynamic Security Assessment Study
        </div>
        
        <div class="abstract">
            <div class="abstract-title">Abstract</div>
            <p>
                This report presents a comprehensive security and quality analysis of Application #{app_num} 
                generated using the {model} large language model. The analysis employs {tools_count} automated 
                assessment tools across multiple dimensions including static code analysis, security vulnerability 
                detection, and code quality metrics. A total of <i>n</i> = {total_findings} findings were identified, 
                categorized by severity levels according to industry-standard CVSS scoring methodology.
                The results demonstrate the efficacy of automated tooling in evaluating LLM-generated code artifacts.
            </p>
        </div>
        
        <div class="metadata">
            <div class="metadata-item">
                <span class="metadata-label">Report ID:</span>
                <span class="metadata-value">{report.report_id}</span>
            </div>
            <div class="metadata-item">
                <span class="metadata-label">Model Under Test:</span>
                <span class="metadata-value">{model}</span>
            </div>
            <div class="metadata-item">
                <span class="metadata-label">Application Number:</span>
                <span class="metadata-value">{app_num}</span>
            </div>
            <div class="metadata-item">
                <span class="metadata-label">Analysis Date:</span>
                <span class="metadata-value">{timestamp[:10]}</span>
            </div>
            <div class="metadata-item">
                <span class="metadata-label">Sample Size:</span>
                <span class="metadata-value"><i>n</i> = {total_findings}</span>
            </div>
        </div>

        <h2>Quantitative Results</h2>
        
        <p>
            The automated analysis identified {total_findings} distinct findings across all severity categories. 
            The distribution follows a severity-based taxonomy where findings are classified as Critical, High, 
            Medium, or Low based on potential impact and exploitability factors.
        </p>
        
        <div class="stats-table">
            <div class="stat-row">
                <span class="stat-label">Critical Severity Findings:</span>
                <span class="stat-value">{severity_counts['critical']}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">High Severity Findings:</span>
                <span class="stat-value">{severity_counts['high']}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Medium Severity Findings:</span>
                <span class="stat-value">{severity_counts['medium']}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Low Severity Findings:</span>
                <span class="stat-value">{severity_counts['low']}</span>
            </div>
            <div class="stat-row" style="border-top: 2pt solid #000; margin-top: 5pt; padding-top: 5pt;">
                <span class="stat-label">Total Findings:</span>
                <span class="stat-value">{total_findings}</span>
            </div>
        </div>
        
        <div class="notation">
            <div class="notation-title">Notation</div>
            Let <i>F</i> denote the set of all findings where |<i>F</i>| = {total_findings}. 
            The severity distribution can be expressed as: 
            <i>F</i> = <i>F<sub>critical</sub></i> ∪ <i>F<sub>high</sub></i> ∪ <i>F<sub>medium</sub></i> ∪ <i>F<sub>low</sub></i>, 
            where |<i>F<sub>critical</sub></i>| = {severity_counts['critical']}, 
            |<i>F<sub>high</sub></i>| = {severity_counts['high']}, 
            |<i>F<sub>medium</sub></i>| = {severity_counts['medium']}, 
            |<i>F<sub>low</sub></i>| = {severity_counts['low']}.
        </div>

        <h2>Analysis Methodology</h2>
        
        <p>
            The assessment employed a multi-tool approach utilizing {tools_count} distinct static and dynamic 
            analysis instruments. Each tool operates with specific detection algorithms optimized for particular 
            vulnerability classes and code quality metrics.
        </p>
        
        <table>
            <caption>Table I: Analysis Tools and Detection Results</caption>
            <thead>
                <tr>
                    <th>Tool Name</th>
                    <th>Status</th>
                    <th>Findings (<i>n</i>)</th>
                    <th>Success Rate</th>
                </tr>
            </thead>
            <tbody>"""
    
    for tool_name, tool_data in tools.items():
        status = tool_data.get('status', 'unknown')
        count = tool_data.get('findings_count', 0)
        success = '✓' if status == 'success' else '✗'
        html += f"""
                <tr>
                    <td><code>{tool_name}</code></td>
                    <td>{success} {status}</td>
                    <td>{count}</td>
                    <td>{('100%' if status == 'success' else 'N/A')}</td>
                </tr>"""
    
    html += f"""
            </tbody>
        </table>

        <h2>Detailed Findings Enumeration</h2>
        
        <p>
            This section enumerates all identified security vulnerabilities and code quality issues. 
            Each finding is indexed sequentially and includes severity classification, technical description, 
            and source code location metadata.
        </p>
        
        <ul class="findings-list">"""
    
    for idx, finding in enumerate(findings[:50], 1):  # Limit to 50 for HTML
        severity = finding.get('severity', 'low').lower()
        title = finding.get('title', 'Untitled Finding')
        desc = finding.get('description', 'No description available')[:300]
        location = finding.get('location', '')
        
        html += f"""
            <li class="finding-item {severity}">
                <div class="finding-title">
                    <span class="severity-{severity}">{severity.upper()}</span>: {title}
                </div>
                <div class="finding-desc">{desc}</div>
                {f'<div class="finding-location">Location: <code>{location}</code></div>' if location else ''}
            </li>"""
    
    if len(findings) > 50:
        html += f"""
            <li class="finding-item low">
                <div class="finding-title">Additional Findings</div>
                <div class="finding-desc">
                    {len(findings) - 50} additional findings omitted for brevity. 
                    Complete results available in structured data format.
                </div>
            </li>"""
    
    html += f"""
        </ul>
        
        <h2>Discussion</h2>
        
        <p>
            The analysis reveals significant variance in security posture across the evaluated codebase. 
            The presence of {severity_counts['critical'] + severity_counts['high']} high-impact vulnerabilities 
            suggests opportunities for improvement in the code generation model's security awareness. 
            The distribution of findings across severity categories provides quantitative metrics for 
            comparative evaluation against alternative models or generation strategies.
        </p>
        
        <h2>Conclusions</h2>
        
        <p>
            This automated assessment demonstrates that while LLM-generated code exhibits functional capabilities, 
            security considerations require systematic verification through multi-tool analysis. The methodology 
            presented herein provides a reproducible framework for evaluating code security at scale, applicable 
            to comparative studies of different generative models or prompt engineering strategies.
        </p>
        
        <footer>
            <p><strong>Report Metadata</strong></p>
            <p>Document ID: {report.report_id} | Generated: {timestamp[:19]} UTC</p>
            <p class="citation">
                Generated by ThesisAppRework Automated Analysis System v1.0
            </p>
        </footer>
    </div>
</body>
</html>"""
    
    return html


def _render_model_comparison_html(report, data: Dict[str, Any]) -> str:
    """Render model comparison report as HTML."""
    models = data.get('models', [])
    timestamp = data.get('timestamp', datetime.now().isoformat())
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report.title}</title>
    {_get_base_css()}
</head>
<body>
    <div class="container">
        <h1>🔄 {report.title}</h1>
        
        <div class="metadata">
            <div class="metadata-item">
                <div class="metadata-label">Report ID</div>
                <div class="metadata-value">{report.report_id}</div>
            </div>
            <div class="metadata-item">
                <div class="metadata-label">Models Compared</div>
                <div class="metadata-value">{len(models)}</div>
            </div>
            <div class="metadata-item">
                <div class="metadata-label">Generated</div>
                <div class="metadata-value">{timestamp[:19]}</div>
            </div>
        </div>

        <h2>Model Comparison</h2>
        <table>
            <thead>
                <tr>
                    <th>Model</th>
                    <th>Task ID</th>
                    <th>Total Findings</th>
                    <th>Critical</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>"""
    
    for model in models:
        model_slug = model.get('model_slug', 'Unknown')
        task_id = model.get('task_id', 'N/A')[:12]
        findings = model.get('findings', [])
        total = len(findings)
        critical = len([f for f in findings if f.get('severity') == 'critical'])
        
        html += f"""
                <tr>
                    <td><strong>{model_slug}</strong></td>
                    <td><code>{task_id}</code></td>
                    <td>{total}</td>
                    <td><span class="badge badge-danger">{critical}</span></td>
                    <td><span class="badge badge-success">Completed</span></td>
                </tr>"""
    
    html += f"""
            </tbody>
        </table>

        <footer>
            <p>Generated by ThesisAppRework Report System</p>
            <p>Report ID: {report.report_id} • {timestamp}</p>
        </footer>
    </div>
</body>
</html>"""
    
    return html


def _render_executive_summary_html(report, data: Dict[str, Any]) -> str:
    """Render executive summary report as HTML."""
    timestamp = data.get('timestamp', datetime.now().isoformat())
    stats = data.get('statistics', {})
    
    total_apps = stats.get('total_applications', 0)
    total_tasks = stats.get('total_analysis_tasks', 0)
    total_findings = stats.get('total_findings', 0)
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report.title}</title>
    {_get_base_css()}
</head>
<body>
    <div class="container">
        <h1>📈 {report.title}</h1>
        
        <div class="metadata">
            <div class="metadata-item">
                <div class="metadata-label">Report ID</div>
                <div class="metadata-value">{report.report_id}</div>
            </div>
            <div class="metadata-item">
                <div class="metadata-label">Period</div>
                <div class="metadata-value">Last 30 Days</div>
            </div>
            <div class="metadata-item">
                <div class="metadata-label">Generated</div>
                <div class="metadata-value">{timestamp[:19]}</div>
            </div>
        </div>

        <h2>Key Metrics</h2>
        <div class="stat-grid">
            <div class="stat-card blue">
                <div class="stat-label">Total Applications</div>
                <div class="stat-value">{total_apps}</div>
            </div>
            <div class="stat-card green">
                <div class="stat-label">Analysis Tasks</div>
                <div class="stat-value">{total_tasks}</div>
            </div>
            <div class="stat-card orange">
                <div class="stat-label">Total Findings</div>
                <div class="stat-value">{total_findings}</div>
            </div>
        </div>

        <h2>Analysis Summary</h2>
        <div style="background: #f8f9fa; padding: 20px; border-radius: 8px;">
            <p style="font-size: 16px; line-height: 1.8;">
                This executive summary covers analysis activities over the past 30 days.
                The system has processed <strong>{total_apps}</strong> applications and completed 
                <strong>{total_tasks}</strong> analysis tasks, identifying <strong>{total_findings}</strong> 
                total findings across all severity levels.
            </p>
        </div>

        <footer>
            <p>Generated by ThesisAppRework Report System</p>
            <p>Report ID: {report.report_id} • {timestamp}</p>
        </footer>
    </div>
</body>
</html>"""
    
    return html


def _render_tool_effectiveness_html(report, data: Dict[str, Any]) -> str:
    """Render tool effectiveness report as HTML."""
    return _render_default_html(report, data)


def _render_default_html(report, data: Dict[str, Any]) -> str:
    """Render default report as HTML."""
    timestamp = data.get('timestamp', datetime.now().isoformat())
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report.title}</title>
    {_get_base_css()}
</head>
<body>
    <div class="container">
        <h1>📄 {report.title}</h1>
        
        <div class="metadata">
            <div class="metadata-item">
                <div class="metadata-label">Report ID</div>
                <div class="metadata-value">{report.report_id}</div>
            </div>
            <div class="metadata-item">
                <div class="metadata-label">Type</div>
                <div class="metadata-value">{report.report_type}</div>
            </div>
            <div class="metadata-item">
                <div class="metadata-label">Generated</div>
                <div class="metadata-value">{timestamp[:19]}</div>
            </div>
        </div>

        <h2>Report Data</h2>
        <pre style="background: #f8f9fa; padding: 20px; border-radius: 8px; overflow: auto;">
{str(data)[:1000]}
        </pre>

        <footer>
            <p>Generated by ThesisAppRework Report System</p>
            <p>Report ID: {report.report_id} • {timestamp}</p>
        </footer>
    </div>
</body>
</html>"""
    
    return html
