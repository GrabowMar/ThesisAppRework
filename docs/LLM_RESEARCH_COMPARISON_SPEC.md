# LLM Model Research - Data Comparison Specification

## Objective
Create easily comparable data structures for analyzing differences between LLM models in code generation quality, focusing on security, performance, code quality, and requirements compliance.

## Key Metrics for Research Comparison

### 1. Model Metadata
- Model name/slug
- Provider (OpenAI, Anthropic, X.AI, etc.)
- App number
- Analysis timestamp
- Total execution time

### 2. Security Metrics
- **Tool Coverage**: Which security tools ran successfully
- **Vulnerability Counts by Severity**: Critical/High/Medium/Low
- **Vulnerability Types**: SQL injection, XSS, CSRF, insecure dependencies, etc.
- **Tool-Specific Results**:
  - Bandit: Python security issues
  - Safety: Dependency vulnerabilities
  - Semgrep: Pattern-based security issues
  - ZAP: Dynamic web vulnerabilities
  - npm audit: JavaScript dependencies

### 3. Code Quality Metrics
- **Linting Issues**: By severity (error/warning/info)
- **Type Safety**: MyPy/TypeScript errors
- **Dead Code**: Vulture unused code detection
- **Code Smells**: Complexity, duplication, long functions
- **Tool-Specific Results**:
  - PyLint: Python style and errors
  - MyPy: Python type checking
  - ESLint: JavaScript linting
  - Flake8: Python style guide
  - Prettier: Formatting issues

### 4. Performance Metrics
- **Response Times**: Min/Avg/Max/P95/P99
- **Throughput**: Requests per second
- **Error Rates**: Failed requests percentage
- **Concurrency Performance**: Under load behavior
- **Tool-Specific Results**:
  - Apache Bench: HTTP load testing
  - Locust: User simulation
  - aiohttp: Async performance
  - cURL: Basic connectivity

### 5. Requirements Compliance
- **Total Requirements**: Count
- **Met Requirements**: Count and percentage
- **Not Met Requirements**: Count and percentage
- **High-Priority Gaps**: Critical missing features
- **Feature Categories**:
  - Authentication/Authorization
  - Data validation
  - Error handling
  - API endpoints
  - Frontend components
  - Database operations

### 6. Structural Quality
- **File Organization**: File counts by type
- **Docker/Container**: Proper containerization
- **Configuration**: Presence of key config files
- **Dependencies**: Package management quality
- **Documentation**: README, comments

### 7. Tool Execution Summary
For each tool, track:
- **Status**: success/error/skipped
- **Execution Time**: Duration in seconds
- **Files Analyzed**: Count
- **Issues Found**: Total count
- **Error Messages**: If failed
- **Configuration Used**: Tool settings applied

## Comparison Data Structure

```json
{
  "comparison_metadata": {
    "generated_at": "ISO-8601",
    "models_compared": ["model1", "model2", ...],
    "apps_analyzed": [1, 2, 3],
    "analysis_types": ["security", "comprehensive"],
    "comparison_version": "1.0"
  },
  "models": {
    "anthropic_claude-4.5-haiku": {
      "apps": {
        "1": {
          "security": {...},
          "quality": {...},
          "performance": {...},
          "requirements": {...},
          "tools": {...}
        }
      },
      "aggregates": {
        "avg_security_score": 85.5,
        "avg_quality_score": 78.3,
        "avg_requirements_compliance": 82.1,
        "total_critical_issues": 5,
        "total_high_issues": 12
      }
    }
  },
  "cross_model_comparison": {
    "security_ranking": [...],
    "quality_ranking": [...],
    "performance_ranking": [...],
    "requirements_ranking": [...]
  }
}
```

## Research Questions to Answer

1. **Which model produces the most secure code?**
   - Fewest critical/high security vulnerabilities
   - Best security practices adherence
   - Proper input validation and sanitization

2. **Which model has the best code quality?**
   - Fewest linting errors
   - Best type safety
   - Least dead code
   - Most maintainable structure

3. **Which model creates the fastest applications?**
   - Best response times
   - Highest throughput
   - Lowest error rates
   - Better concurrency handling

4. **Which model best follows requirements?**
   - Highest compliance percentage
   - Fewest high-priority gaps
   - Most complete feature implementation

5. **Which tools are most effective at finding issues?**
   - Tool execution success rates
   - Issue detection rates per tool
   - Tool-specific strengths

6. **How do models compare across different app complexities?**
   - Performance on simple vs complex apps
   - Consistency across multiple apps
   - Learning curve effects

## Export Formats

### For Statistical Analysis
- CSV: Flat table with all metrics
- Excel: Multiple sheets with pivot tables
- JSON: Full structured data

### For Visualization
- Chart-ready JSON with aggregated metrics
- Time-series data for trend analysis
- Comparison matrices

### For Academic Papers
- LaTeX tables
- Markdown reports
- Statistical significance data

## Implementation Plan

### Phase 1: Enhanced Data Extraction ✅
- Extract all tool results comprehensively
- Normalize tool outputs to common schema
- Add missing metrics (file counts, durations, configs)

### Phase 2: Comparison API Endpoint
- `/analysis/api/research/compare` - Cross-model comparison
- `/analysis/api/research/model/<slug>` - Single model analysis
- `/analysis/api/research/export/<format>` - Export data

### Phase 3: Aggregation Service
- Calculate aggregate scores
- Generate rankings
- Compute statistical measures

### Phase 4: Visualization Dashboard
- Charts for metric comparisons
- Radar charts for multi-dimensional analysis
- Trend lines across apps

### Phase 5: Export Service
- CSV generation
- Excel with charts
- PDF reports
- LaTeX academic format
