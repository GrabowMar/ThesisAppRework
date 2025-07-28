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
