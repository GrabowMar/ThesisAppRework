# Research Comparison API - Complete Documentation

## Overview
The Research Comparison API provides comprehensive data extraction and comparison capabilities for analyzing LLM-generated applications. This API is specifically designed for academic research, allowing easy comparison of different models across security, code quality, performance, and requirements compliance metrics.

## Base URL
```
/analysis/api/research
```

## Endpoints

### 1. Get Model Comprehensive Data
**Endpoint**: `GET /analysis/api/research/model/<model_slug>`

**Description**: Retrieve all analysis data for a single model across one or more apps.

**Parameters**:
- `apps` (query, optional): Comma-separated list of app numbers (e.g., `"1,2,3"`)

**Example Request**:
```bash
curl "http://localhost:5000/analysis/api/research/model/anthropic_claude-4.5-haiku-20251001?apps=1,2,3"
```

**Response Structure**:
```json
{
  "model_slug": "anthropic_claude-4.5-haiku-20251001",
  "provider": "Anthropic",
  "apps": {
    "1": {
      "analyses": [
        {
          "task_id": "...",
          "timestamp": "2025-10-19T...",
          "security": {
            "total_issues": 3,
            "by_severity": {"high": 2, "medium": 1},
            "by_tool": {"bandit": 2, "safety": 1},
            "critical_count": 0,
            "high_count": 2,
            "tool_results": {
              "bandit": {"executed": true, "status": "success", "total_issues": 2},
              "safety": {"executed": true, "status": "success", "total_issues": 1}
            }
          },
          "quality": {
            "total_issues": 5,
            "error_count": 2,
            "warning_count": 3,
            "type_errors": 1,
            "dead_code": 0,
            "tool_results": {
              "pylint": {"executed": true, "total_issues": 3},
              "mypy": {"executed": true, "total_issues": 2}
            }
          },
          "performance": {
            "available": true,
            "avg_response_time_ms": 125.5,
            "avg_requests_per_sec": 80.2,
            "success_rate": 98.5,
            "endpoint_results": [...]
          },
          "requirements": {
            "available": true,
            "total_requirements": 10,
            "met": 8,
            "compliance_percentage": 80.0,
            "high_priority_gaps": 1
          },
          "structure": {
            "total_files": 15,
            "python_files": 5,
            "javascript_files": 8,
            "has_dockerfile": true
          },
          "tools": {
            "bandit": {"executed": true, "status": "success", "issues_found": 2},
            "mypy": {"executed": true, "status": "success", "issues_found": 1}
          }
        }
      ]
    }
  },
  "aggregates": {
    "total_analyses": 3,
    "apps_analyzed": 3,
    "security": {
      "avg_total_issues": 2.5,
      "total_critical": 0,
      "total_high": 5
    },
    "quality": {
      "avg_total_issues": 4.2,
      "avg_errors": 1.8
    },
    "performance": {
      "avg_response_time_ms": 130.2,
      "avg_requests_per_sec": 75.5
    },
    "requirements": {
      "avg_compliance": 78.5
    }
  }
}
```

### 2. Compare Models
**Endpoint**: `GET|POST /analysis/api/research/compare`

**Description**: Compare multiple models across all metrics with rankings.

**GET Parameters**:
- `models` (required): Comma-separated model slugs
- `apps` (optional): Comma-separated app numbers

**POST Body** (JSON):
```json
{
  "models": ["anthropic_claude-4.5-haiku-20251001", "openai_gpt-4"],
  "apps": [1, 2, 3]
}
```

**Example Request**:
```bash
# GET
curl "http://localhost:5000/analysis/api/research/compare?models=anthropic_claude-4.5-haiku-20251001,openai_gpt-4&apps=1,2,3"

# POST
curl -X POST "http://localhost:5000/analysis/api/research/compare" \
  -H "Content-Type: application/json" \
  -d '{"models": ["anthropic_claude-4.5-haiku-20251001", "openai_gpt-4"], "apps": [1,2,3]}'
```

**Response Structure**:
```json
{
  "comparison_metadata": {
    "generated_at": "2025-10-19T20:00:00",
    "models_compared": ["anthropic_claude-4.5-haiku-20251001", "openai_gpt-4"],
    "apps_analyzed": [1, 2, 3],
    "comparison_version": "1.0"
  },
  "models": {
    "anthropic_claude-4.5-haiku-20251001": { /* Full model data */ },
    "openai_gpt-4": { /* Full model data */ }
  },
  "cross_model_comparison": {
    "security_ranking": [
      {"model": "openai_gpt-4", "score": 15.0},
      {"model": "anthropic_claude-4.5-haiku-20251001", "score": 22.0}
    ],
    "quality_ranking": [
      {"model": "openai_gpt-4", "score": 3.5},
      {"model": "anthropic_claude-4.5-haiku-20251001", "score": 4.2}
    ],
    "performance_ranking": [
      {"model": "openai_gpt-4", "score": 120.5},
      {"model": "anthropic_claude-4.5-haiku-20251001", "score": 130.2}
    ],
    "requirements_ranking": [
      {"model": "anthropic_claude-4.5-haiku-20251001", "score": 85.0},
      {"model": "openai_gpt-4", "score": 78.5}
    ]
  }
}
```

### 3. Export to CSV
**Endpoint**: `GET|POST /analysis/api/research/export/csv`

**Description**: Export comparison data as CSV for statistical analysis in R, Python, Excel, etc.

**Parameters**: Same as compare endpoint

**Example Request**:
```bash
curl "http://localhost:5000/analysis/api/research/export/csv?models=anthropic_claude-4.5-haiku-20251001,openai_gpt-4" \
  -o model_comparison.csv
```

**CSV Format**:
```csv
Model,Provider,App,Analysis Type,Security Total,Security Critical,Security High,Security Medium,Security Low,Quality Total,Quality Errors,Quality Warnings,Quality Type Errors,Quality Dead Code,Performance Avg Response (ms),Performance Requests/sec,Performance Success Rate,Requirements Total,Requirements Met,Requirements Compliance %,Structural Total Files,Structural Python Files,Structural JS Files,Tools Used Count,Tools Skipped Count
anthropic_claude-4.5-haiku-20251001,Anthropic,1,comprehensive,3,0,2,1,0,5,2,3,1,0,125.5,80.2,98.5,10,8,80.0,15,5,8,6,2
anthropic_claude-4.5-haiku-20251001,Anthropic,2,comprehensive,2,0,1,1,0,4,1,3,2,0,130.2,75.5,97.8,10,9,90.0,16,6,7,6,2
```

### 4. Export Summary (Markdown)
**Endpoint**: `GET /analysis/api/research/export/summary`

**Description**: Export high-level summary suitable for academic papers and reports.

**Parameters**:
- `models` (required): Comma-separated model slugs

**Example Request**:
```bash
curl "http://localhost:5000/analysis/api/research/export/summary?models=anthropic_claude-4.5-haiku-20251001,openai_gpt-4" \
  -o comparison_summary.md
```

**Output Format**: Markdown with:
- Models analyzed
- Rankings (security, quality, performance, requirements)
- Aggregate metrics per model
- Summary statistics

### 5. Tools Summary
**Endpoint**: `GET /analysis/api/research/tools/summary`

**Description**: Get summary of tool execution across all models and apps, including success rates and issue detection rates.

**Example Request**:
```bash
curl "http://localhost:5000/analysis/api/research/tools/summary"
```

**Response Structure**:
```json
{
  "tool_summary": {
    "bandit": {
      "total_executions": 50,
      "success_rate": 94.0,
      "failure_rate": 6.0,
      "skip_rate": 0.0,
      "total_issues_found": 125,
      "avg_issues_per_execution": 2.65,
      "avg_execution_time": 1.5,
      "min_execution_time": 0.8,
      "max_execution_time": 3.2
    },
    "mypy": {
      "total_executions": 50,
      "success_rate": 100.0,
      "total_issues_found": 80,
      "avg_issues_per_execution": 1.6
    }
  },
  "total_tools": 12,
  "total_tasks_analyzed": 50
}
```

## Data Metrics Explanation

### Security Metrics
- **total_issues**: Total number of security findings
- **by_severity**: Breakdown by critical/high/medium/low
- **by_tool**: Findings per security tool (Bandit, Safety, ZAP, etc.)
- **by_type**: Vulnerability types (SQL injection, XSS, etc.)
- **tool_results**: Detailed results from each tool

**Security Score** (lower is better): `critical_count * 10 + high_count`

### Quality Metrics
- **total_issues**: Total code quality issues
- **error_count**: High-severity quality issues
- **warning_count**: Medium-severity quality issues
- **type_errors**: MyPy type checking errors
- **dead_code**: Vulture unused code detections
- **tool_results**: Results from PyLint, ESLint, MyPy, etc.

**Quality Score** (lower is better): `avg_total_issues`

### Performance Metrics
- **avg_response_time_ms**: Average HTTP response time
- **min/max_response_time_ms**: Response time range
- **avg_requests_per_sec**: Throughput capacity
- **total_requests/total_failed**: Request counts
- **success_rate**: Percentage of successful requests
- **endpoint_results**: Per-endpoint performance data

**Performance Score** (lower is better): `avg_response_time_ms`

### Requirements Compliance
- **total_requirements**: Number of requirements checked
- **met/not_met**: Counts of satisfied/unsatisfied requirements
- **compliance_percentage**: Overall compliance rate
- **by_priority**: Breakdown by HIGH/MEDIUM/LOW priority
- **high_priority_gaps**: Critical missing features

**Requirements Score** (higher is better): `compliance_percentage`

### Structural Quality
- **total_files**: Number of source files
- **file_counts**: Breakdown by file type (Python, JS, CSS, etc.)
- **has_***: Presence of key files (Dockerfile, requirements.txt, etc.)

### Tool Execution Details
- **executed**: Whether tool ran
- **status**: success/error/skipped
- **issues_found**: Number of issues detected
- **duration_seconds**: Execution time
- **error**: Error message if failed

## Usage Examples

### Python Research Script
```python
import requests
import pandas as pd

# Get comparison data
response = requests.get(
    'http://localhost:5000/analysis/api/research/compare',
    params={
        'models': 'anthropic_claude-4.5-haiku-20251001,openai_gpt-4,x-ai_grok-beta',
        'apps': '1,2,3'
    }
)
comparison = response.json()

# Extract security scores
security_data = []
for model, data in comparison['models'].items():
    aggregates = data['aggregates']
    security = aggregates.get('security', {})
    security_data.append({
        'model': model,
        'avg_issues': security.get('avg_total_issues', 0),
        'critical': security.get('total_critical', 0),
        'high': security.get('total_high', 0)
    })

df = pd.DataFrame(security_data)
print(df)

# Download CSV for detailed analysis
csv_response = requests.get(
    'http://localhost:5000/analysis/api/research/export/csv',
    params={'models': 'anthropic_claude-4.5-haiku-20251001,openai_gpt-4'}
)
with open('comparison.csv', 'wb') as f:
    f.write(csv_response.content)

# Load into pandas
df_detailed = pd.read_csv('comparison.csv')

# Statistical analysis
print("Security Issues by Model:")
print(df_detailed.groupby('Model')['Security Total'].agg(['mean', 'std', 'min', 'max']))

print("\nQuality Issues by Model:")
print(df_detailed.groupby('Model')['Quality Total'].agg(['mean', 'std', 'min', 'max']))
```

### R Statistical Analysis
```r
library(httr)
library(jsonlite)
library(dplyr)
library(ggplot2)

# Get CSV data
response <- GET("http://localhost:5000/analysis/api/research/export/csv?models=anthropic_claude-4.5-haiku-20251001,openai_gpt-4")
data <- read.csv(text = content(response, "text"))

# Statistical tests
# Compare security issues between models
t.test(data$Security.Total ~ data$Model)

# ANOVA for multiple models
aov_result <- aov(Security.Total ~ Model, data = data)
summary(aov_result)

# Visualization
ggplot(data, aes(x = Model, y = Security.Total, fill = Model)) +
  geom_boxplot() +
  theme_minimal() +
  labs(title = "Security Issues by Model", y = "Total Security Issues")

# Correlation analysis
cor.test(data$Security.Total, data$Quality.Total)
```

### Academic Paper LaTeX
```latex
\begin{table}[h]
\centering
\caption{LLM Model Comparison Results}
\begin{tabular}{lcccc}
\hline
Model & Security & Quality & Performance & Requirements \\
& (Issues) & (Issues) & (ms) & (\%) \\
\hline
Claude 4.5 Haiku & 2.5 $\pm$ 1.2 & 4.2 $\pm$ 2.1 & 130.2 & 85.0 \\
GPT-4 & 3.8 $\pm$ 1.5 & 3.5 $\pm$ 1.8 & 120.5 & 78.5 \\
Grok Beta & 4.2 $\pm$ 2.0 & 5.1 $\pm$ 2.5 & 145.8 & 72.3 \\
\hline
\end{tabular}
\end{table}
```

## Error Handling

All endpoints return JSON error responses:

```json
{
  "error": "Error description"
}
```

**HTTP Status Codes**:
- `200`: Success
- `400`: Bad request (invalid parameters)
- `404`: Not found
- `500`: Internal server error
- `503`: Service unavailable

## Rate Limiting

No rate limiting currently implemented. For large-scale analysis, consider batch processing.

## Data Freshness

All data is pulled directly from the database. To ensure fresh data, run analysis on apps before querying.

## Best Practices

1. **Use specific app numbers** when comparing models to ensure fair comparison
2. **Export to CSV** for detailed statistical analysis in R/Python
3. **Use markdown summary** for quick overview in reports
4. **Check tool summary** to understand which tools are most effective
5. **Aggregate metrics** provide quick comparison, but review app-level data for details

## Research Questions Answerable

### Which model produces the most secure code?
```bash
curl "/analysis/api/research/compare?models=model1,model2" | jq '.cross_model_comparison.security_ranking'
```

### Which model has best code quality?
```bash
curl "/analysis/api/research/compare?models=model1,model2" | jq '.cross_model_comparison.quality_ranking'
```

### Which tools find the most issues?
```bash
curl "/analysis/api/research/tools/summary" | jq '.tool_summary | to_entries | sort_by(.value.avg_issues_per_execution) | reverse'
```

### How does performance scale with app complexity?
Export CSV and analyze correlation between file counts and performance metrics.

### Are there patterns in requirements compliance?
Export full model data and analyze which requirement categories are most often missing.

## Future Enhancements

- [ ] Export to Excel with charts
- [ ] Statistical significance calculations
- [ ] Trend analysis over time
- [ ] Machine learning model for predicting issues
- [ ] Interactive web dashboard
- [ ] Real-time comparison updates
