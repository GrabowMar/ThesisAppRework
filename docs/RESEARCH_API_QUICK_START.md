# Research API Quick Start Guide

## Overview
The Research Comparison API enables comprehensive data extraction and cross-model comparison for LLM-generated application analysis. Perfect for academic research, papers, and statistical analysis.

## Quick Test (PowerShell)
```powershell
# 1. Get comprehensive data for one model
curl "http://localhost:5000/analysis/api/research/model/anthropic_claude-4.5-haiku-20251001" | ConvertFrom-Json

# 2. Compare multiple models
curl "http://localhost:5000/analysis/api/research/compare?models=anthropic_claude-4.5-haiku-20251001,x-ai_grok-beta" | ConvertFrom-Json

# 3. Export to CSV for statistical analysis
Invoke-WebRequest -Uri "http://localhost:5000/analysis/api/research/export/csv?models=anthropic_claude-4.5-haiku-20251001,x-ai_grok-beta" -OutFile "comparison.csv"

# 4. Get markdown summary
curl "http://localhost:5000/analysis/api/research/export/summary?models=anthropic_claude-4.5-haiku-20251001,x-ai_grok-beta" > summary.md

# 5. Get tool effectiveness statistics
curl "http://localhost:5000/analysis/api/research/tools/summary" | ConvertFrom-Json
```

## Quick Test (curl/bash)
```bash
# 1. Get comprehensive data for one model
curl "http://localhost:5000/analysis/api/research/model/anthropic_claude-4.5-haiku-20251001" | jq .

# 2. Compare multiple models
curl "http://localhost:5000/analysis/api/research/compare?models=anthropic_claude-4.5-haiku-20251001,x-ai_grok-beta" | jq .

# 3. Export to CSV
curl "http://localhost:5000/analysis/api/research/export/csv?models=anthropic_claude-4.5-haiku-20251001,x-ai_grok-beta" > comparison.csv

# 4. Get markdown summary
curl "http://localhost:5000/analysis/api/research/export/summary?models=anthropic_claude-4.5-haiku-20251001,x-ai_grok-beta" > summary.md

# 5. Get tool statistics
curl "http://localhost:5000/analysis/api/research/tools/summary" | jq .
```

## Common Research Workflows

### 1. Model Security Comparison
```powershell
# Get security comparison with rankings
$comparison = curl -s "http://localhost:5000/analysis/api/research/compare?models=model1,model2,model3" | ConvertFrom-Json

# Show security rankings
$comparison.cross_model_comparison.security_ranking | Format-Table

# Export detailed security data
Invoke-WebRequest -Uri "http://localhost:5000/analysis/api/research/export/csv?models=model1,model2,model3" -OutFile "security_analysis.csv"

# Analyze in Excel or R/Python
```

### 2. Code Quality Analysis
```powershell
# Get quality metrics for models
$models = "anthropic_claude-4.5-haiku-20251001", "openai_gpt-4", "x-ai_grok-beta"
$data = curl -s "http://localhost:5000/analysis/api/research/compare?models=$($models -join ',')" | ConvertFrom-Json

# Extract quality rankings
$data.cross_model_comparison.quality_ranking
```

### 3. Performance Benchmarking
```powershell
# Compare performance across models
$comparison = curl -s "http://localhost:5000/analysis/api/research/compare?models=model1,model2" | ConvertFrom-Json

# Show performance rankings (lower response time = better)
$comparison.cross_model_comparison.performance_ranking | Format-Table
```

### 4. Requirements Compliance Study
```powershell
# Get requirements compliance comparison
$comparison = curl -s "http://localhost:5000/analysis/api/research/compare?models=model1,model2,model3" | ConvertFrom-Json

# Show compliance rankings (higher percentage = better)
$comparison.cross_model_comparison.requirements_ranking | Format-Table
```

### 5. Tool Effectiveness Research
```powershell
# Get tool statistics
$tools = curl -s "http://localhost:5000/analysis/api/research/tools/summary" | ConvertFrom-Json

# Find most effective tools (highest issue detection rate)
$tools.tool_summary.PSObject.Properties | 
  Sort-Object {$_.Value.avg_issues_per_execution} -Descending | 
  Select-Object -First 10
```

## Python Research Script Example
```python
import requests
import pandas as pd
import matplotlib.pyplot as plt

# Get comparison data
models = "anthropic_claude-4.5-haiku-20251001,openai_gpt-4,x-ai_grok-beta"
response = requests.get(
    f'http://localhost:5000/analysis/api/research/compare?models={models}'
)
data = response.json()

# Extract security scores
security_data = []
for ranking in data['cross_model_comparison']['security_ranking']:
    security_data.append({
        'model': ranking['model'],
        'score': ranking['score']
    })

df_security = pd.DataFrame(security_data)

# Plot comparison
plt.figure(figsize=(10, 6))
plt.bar(df_security['model'], df_security['score'])
plt.title('Security Score Comparison (Lower is Better)')
plt.xlabel('Model')
plt.ylabel('Security Score')
plt.xticks(rotation=45, ha='right')
plt.tight_layout()
plt.savefig('security_comparison.png')

# Download CSV for detailed analysis
csv_response = requests.get(
    f'http://localhost:5000/analysis/api/research/export/csv?models={models}'
)
with open('detailed_comparison.csv', 'wb') as f:
    f.write(csv_response.content)

# Load and analyze
df = pd.read_csv('detailed_comparison.csv')

# Statistical analysis
print("=== Security Issues by Model ===")
print(df.groupby('Model')['Security Total'].agg(['mean', 'std', 'min', 'max']))

print("\n=== Quality Issues by Model ===")
print(df.groupby('Model')['Quality Total'].agg(['mean', 'std', 'min', 'max']))

print("\n=== Performance by Model ===")
print(df.groupby('Model')['Performance Avg Response (ms)'].agg(['mean', 'std', 'min', 'max']))
```

## R Statistical Analysis Example
```r
library(httr)
library(jsonlite)
library(dplyr)
library(ggplot2)

# Get CSV data
models <- "anthropic_claude-4.5-haiku-20251001,openai_gpt-4,x-ai_grok-beta"
url <- paste0("http://localhost:5000/analysis/api/research/export/csv?models=", models)
response <- GET(url)
data <- read.csv(text = content(response, "text"))

# T-test for security differences
model1_data <- filter(data, Model == "anthropic_claude-4.5-haiku-20251001")
model2_data <- filter(data, Model == "openai_gpt-4")
t.test(model1_data$Security.Total, model2_data$Security.Total)

# ANOVA for multiple models
aov_result <- aov(Security.Total ~ Model, data = data)
summary(aov_result)

# Visualization
ggplot(data, aes(x = Model, y = Security.Total, fill = Model)) +
  geom_boxplot() +
  theme_minimal() +
  labs(
    title = "Security Issues by Model",
    y = "Total Security Issues",
    x = "Model"
  ) +
  theme(axis.text.x = element_text(angle = 45, hjust = 1))

# Correlation analysis
cor_matrix <- cor(data[, c("Security.Total", "Quality.Total", "Quality.Errors")])
print(cor_matrix)
```

## Data Interpretation Guide

### Security Score (Lower is Better)
- **Score Formula**: `critical_count * 10 + high_count`
- **Interpretation**:
  - 0-10: Excellent security
  - 11-20: Good security
  - 21-50: Moderate security concerns
  - 51+: Significant security issues

### Quality Score (Lower is Better)
- **Score Formula**: `avg_total_issues`
- **Interpretation**:
  - 0-5: Excellent code quality
  - 6-15: Good code quality
  - 16-30: Moderate quality issues
  - 31+: Poor code quality

### Performance Score (Lower is Better)
- **Score Formula**: `avg_response_time_ms`
- **Interpretation**:
  - 0-100ms: Excellent performance
  - 101-200ms: Good performance
  - 201-500ms: Acceptable performance
  - 501+ms: Poor performance

### Requirements Compliance (Higher is Better)
- **Score Formula**: `compliance_percentage`
- **Interpretation**:
  - 90-100%: Excellent compliance
  - 80-89%: Good compliance
  - 70-79%: Acceptable compliance
  - 0-69%: Poor compliance

## Common Queries

### Which model is most secure?
```powershell
$comp = curl -s "http://localhost:5000/analysis/api/research/compare?models=model1,model2,model3" | ConvertFrom-Json
$comp.cross_model_comparison.security_ranking[0].model
```

### Which model has best code quality?
```powershell
$comp = curl -s "http://localhost:5000/analysis/api/research/compare?models=model1,model2,model3" | ConvertFrom-Json
$comp.cross_model_comparison.quality_ranking[0].model
```

### Which model is fastest?
```powershell
$comp = curl -s "http://localhost:5000/analysis/api/research/compare?models=model1,model2,model3" | ConvertFrom-Json
$comp.cross_model_comparison.performance_ranking[0].model
```

### Which model best meets requirements?
```powershell
$comp = curl -s "http://localhost:5000/analysis/api/research/compare?models=model1,model2,model3" | ConvertFrom-Json
$comp.cross_model_comparison.requirements_ranking[0].model
```

## Troubleshooting

### No data returned
- Ensure models have been analyzed (check `/analysis/api/tasks`)
- Verify model slugs are correct (use exact slugs from database)
- Check Flask server is running on port 5000

### CSV export is empty
- Ensure model slugs match exactly
- Check that analysis tasks are completed
- Verify results JSON files exist in `results/` directory

### Performance metrics show N/A
- Performance analysis may not be enabled for all tasks
- Check if `performance-tester` service ran successfully
- Verify analysis type includes performance

## Next Steps
1. Run comprehensive analysis on multiple models
2. Export data using CSV endpoint
3. Perform statistical analysis in Python/R
4. Generate visualizations for papers
5. Use markdown summaries for quick reports

For detailed API documentation, see `docs/RESEARCH_API_DOCUMENTATION.md`
