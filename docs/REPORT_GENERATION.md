# Report Generation Service

Comprehensive report generation system for analysis results, model comparisons, tool effectiveness metrics, and executive summaries.

## Features

- **Multiple Report Types**:
  - App Analysis: Detailed analysis of a single generated app
  - Model Comparison: Compare analysis results across multiple AI models
  - Tool Effectiveness: Analyze tool performance and success rates
  - Executive Summary: High-level overview with KPIs
  - Custom Reports: Flexible query-based reports

- **Multiple Export Formats**:
  - PDF: Print-ready reports using WeasyPrint
  - HTML: Interactive browser-viewable reports
  - Excel: Multi-sheet workbooks with charts
  - JSON: Machine-readable structured data

- **Features**:
  - Database-tracked report generation
  - File-based report storage
  - Automatic expiration and cleanup
  - Progress tracking
  - Print-optimized styling
  - Static chart generation (matplotlib)

## Installation

Dependencies are already added to `requirements.txt`:

```bash
# Install dependencies
pip install -r requirements.txt

# Run database migration
python migrations/20251112_add_reports_table.py
```

## Usage

### Web UI

1. Navigate to `/reports` to see all generated reports
2. Click "Generate Report" button
3. Select report type, format, and configure parameters
4. Submit to generate the report
5. Download or view the completed report

### API

#### Generate a Report

```bash
POST /api/reports/generate
Content-Type: application/json
Authorization: Bearer <token>

{
  "report_type": "app_analysis",
  "format": "pdf",
  "config": {
    "model_slug": "openai_gpt-4",
    "app_number": 1
  },
  "title": "GPT-4 App #1 Analysis",
  "description": "Security and quality analysis",
  "expires_in_days": 30
}
```

**Response:**
```json
{
  "success": true,
  "report": {
    "report_id": "report_abc123...",
    "status": "completed",
    "file_path": "app_analysis/report_abc123_20251112_143022.pdf",
    "format": "pdf",
    ...
  }
}
```

#### List Reports

```bash
GET /api/reports?report_type=app_analysis&status=completed&limit=20
```

#### Download Report

```bash
GET /api/reports/{report_id}/download
```

Add `?inline=true` to view in browser instead of downloading.

#### Delete Report

```bash
DELETE /api/reports/{report_id}?delete_file=true
```

### Programmatic Usage

```python
from app.services.service_locator import ServiceLocator

# Get service
service_locator = ServiceLocator()
report_service = service_locator.get_report_service()

# Generate app analysis report
report = report_service.generate_report(
    report_type='app_analysis',
    format='pdf',
    config={
        'model_slug': 'openai_gpt-4',
        'app_number': 1
    },
    title='GPT-4 App Analysis',
    user_id=1,
    expires_in_days=30
)

# Check status
print(f"Report {report.report_id}: {report.status}")

# Get file path
if report.status == 'completed':
    file_path = report_service.reports_dir / report.file_path
    print(f"Report saved to: {file_path}")
```

## Report Types

### 1. App Analysis

Detailed analysis of a single generated application.

**Config:**
```json
{
  "model_slug": "openai_gpt-4",
  "app_number": 1,
  "task_id": "task_abc123"  // optional, uses latest if not specified
}
```

**Includes:**
- Analysis summary (model, app, task info)
- Severity distribution
- Tool execution status
- Detailed findings table (up to 100 in print view)
- File locations and line numbers

### 2. Model Comparison

Compare analysis results across multiple AI models.

**Config:**
```json
{
  "model_slugs": ["openai_gpt-4", "anthropic_claude-3-sonnet", "google_gemini-pro"],
  "app_number": 1,
  "date_range": {
    "start": "2025-01-01",
    "end": "2025-12-31"
  }
}
```

**Includes:**
- Aggregated statistics (avg findings, best/worst model)
- Model-by-model comparison table
- Severity breakdown per model
- Tool execution comparison matrix

### 3. Tool Effectiveness

Analyze tool performance across all analyses.

**Config:**
```json
{
  "tools": ["bandit", "eslint", "safety"],  // optional, all tools if not specified
  "date_range": {
    "start": "2025-01-01",
    "end": "2025-12-31"
  }
}
```

**Includes:**
- Tool performance metrics (success rate, avg duration)
- Total findings per tool
- Severity distribution by tool
- Rankings (most findings, highest success rate)

### 4. Executive Summary

High-level overview with KPIs.

**Config:**
```json
{
  "date_range": {
    "start": "2025-01-01",
    "end": "2025-12-31"
  }
}
```

**Includes:**
- Key performance indicators (apps generated, analyses completed, findings)
- Severity distribution
- Generation summary (success/failure rates)
- Model usage statistics
- Key insights and recommendations

### 5. Custom Reports

Flexible reports based on custom queries.

**Config:**
```json
{
  "query_type": "specific_tasks",
  "task_ids": ["task_abc123", "task_def456"]
}
```

## Configuration

### Environment Variables

```bash
# Reports directory (default: <project_root>/reports)
REPORTS_DIR=/path/to/reports

# Optional: Customize report expiration
REPORT_DEFAULT_EXPIRATION_DAYS=30
```

### Service Configuration

The service is automatically registered in `ServiceLocator` during app initialization.

## File Structure

```
reports/
├── app_analysis/
│   ├── report_abc123_20251112_143022.pdf
│   └── report_def456_20251112_150315.html
├── model_comparison/
│   └── report_xyz789_20251112_160530.xlsx
├── tool_effectiveness/
│   └── report_uvw012_20251112_170845.pdf
└── executive_summary/
    └── report_rst345_20251112_180200.pdf
```

## Data Sources

Reports use a **hybrid approach** combining both database and filesystem:

1. **Database (fast queries)**: Metadata, task info, filtering
2. **Filesystem (complete data)**: Full analysis results from `results/{model}/app{N}/task_{id}/`

This ensures:
- Fast report listing and filtering (DB)
- Complete analysis data in reports (filesystem)
- Accurate findings representation (from consolidated task JSON)

## Print Optimization

Reports include print-ready CSS (`report-print.css`) with:
- A4 page size optimization
- Page break control (avoid breaking cards/tables)
- Exact color reproduction
- Optimized font sizes
- Hidden UI elements (buttons, nav, etc.)

**To print/save as PDF from browser:**
1. View HTML report
2. Use browser's Print function (Ctrl+P / Cmd+P)
3. Select "Save as PDF"
4. Ensure "Background graphics" is enabled

## Maintenance

### Cleanup Expired Reports

Manually trigger cleanup:

```bash
POST /api/reports/cleanup/expired
Authorization: Bearer <admin_token>
```

Or via cron job:

```python
from app.services.service_locator import ServiceLocator

service_locator = ServiceLocator()
report_service = service_locator.get_report_service()
count = report_service.cleanup_expired_reports()
print(f"Cleaned up {count} expired reports")
```

### Database Schema

The `reports` table tracks all generated reports:

```sql
CREATE TABLE reports (
    id INTEGER PRIMARY KEY,
    report_id VARCHAR(100) UNIQUE NOT NULL,
    report_type VARCHAR(100) NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    config TEXT NOT NULL,
    format VARCHAR(50) NOT NULL,
    file_path VARCHAR(500),
    file_size INTEGER,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    error_message TEXT,
    progress_percent INTEGER DEFAULT 0,
    created_by INTEGER REFERENCES users(id),
    created_at DATETIME NOT NULL,
    completed_at DATETIME,
    expires_at DATETIME,
    summary TEXT,
    analysis_task_id INTEGER REFERENCES analysis_tasks(id),
    generated_app_id INTEGER REFERENCES generated_applications(id)
);

CREATE INDEX idx_report_type_status ON reports(report_type, status);
CREATE INDEX idx_report_created_at ON reports(created_at);
```

## Extension Points

### Adding New Report Types

1. **Update Service**: Add generator method in `ReportGenerationService`
2. **Create Template**: Add HTML template in `src/templates/pages/reports/`
3. **Update Renderers**: Extend Excel/PDF renderers if needed
4. **Update UI**: Add option to `new_report.html` form

Example:

```python
# In report_generation_service.py
def _generate_security_audit_data(self, config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate data for security audit report."""
    # Your data aggregation logic
    return {
        'vulnerabilities': [...],
        'risk_score': 85,
        ...
    }
```

### Custom Chart Generation

For static charts in PDFs, use matplotlib:

```python
import matplotlib.pyplot as plt
from io import BytesIO
import base64

def generate_severity_chart(severity_data):
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.bar(severity_data.keys(), severity_data.values())
    ax.set_xlabel('Severity')
    ax.set_ylabel('Count')
    
    # Save to base64 for HTML embedding
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
    buffer.seek(0)
    img_data = base64.b64encode(buffer.read()).decode()
    plt.close()
    
    return f'data:image/png;base64,{img_data}'
```

Then in template:
```html
<img src="{{ chart_data }}" alt="Severity Distribution">
```

## Troubleshooting

### WeasyPrint Installation Issues

On Windows, WeasyPrint requires GTK3 runtime:

```bash
# Download and install GTK3 from:
# https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases
```

On Linux:
```bash
sudo apt-get install python3-dev python3-pip python3-setuptools python3-wheel python3-cffi libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info
```

### Missing Fonts in PDF

WeasyPrint uses system fonts. Ensure required fonts are installed:

```python
# In pdf_renderer.py, specify font paths:
from weasyprint.text.fonts import FontConfiguration

font_config = FontConfiguration()
css = CSS(string='''
    @font-face {
        font-family: 'Custom Font';
        src: url('/path/to/font.ttf');
    }
    body { font-family: 'Custom Font', sans-serif; }
''', font_config=font_config)
```

### Large Reports Timeout

For reports with many findings (>1000), increase timeouts:

```python
# In report_generation_service.py
@timeout(seconds=300)  # 5 minutes
def _generate_report_content(self, report: Report) -> None:
    ...
```

Or generate reports asynchronously with background workers (future enhancement).

## Future Enhancements

- [ ] Async report generation with Celery/RQ
- [ ] Real-time progress tracking via WebSockets
- [ ] Interactive charts with Chart.js/Plotly
- [ ] Report templates (save/reuse configurations)
- [ ] Scheduled reports (weekly/monthly)
- [ ] Email report delivery
- [ ] Report annotations and comments
- [ ] Diff reports (compare two analyses)
- [ ] Multi-language support

## API Reference

See full API documentation: `/api/reports` endpoints

- `POST /api/reports/generate` - Create new report
- `GET /api/reports` - List reports
- `GET /api/reports/{report_id}` - Get report details
- `GET /api/reports/{report_id}/download` - Download report file
- `DELETE /api/reports/{report_id}` - Delete report
- `POST /api/reports/cleanup/expired` - Cleanup expired reports (admin)

## License

Part of ThesisApp - See main project LICENSE
