# Analyzer Infrastructure Testing on Real Models

This directory contains comprehensive testing tools for the analyzer infrastructure using real AI-generated models from the `misc/models/` directory.

## 🎯 Overview

The testing infrastructure validates four analyzer services against actual AI-generated applications:

1. **Static Analyzer** (Port 8001): Code quality and security analysis using Bandit, Pylint, ESLint
2. **Dynamic Analyzer** (Port 8002): OWASP ZAP security scanning for running applications  
3. **Performance Tester** (Port 8003): Load testing using Locust
4. **AI Analyzer** (Port 8004): OpenRouter-powered code analysis and requirements checking

## 📊 Database-Driven Testing

All test targets are automatically discovered from the database:
- **PortConfiguration**: Localhost addresses and port assignments for each model/app
- **ModelCapability**: Metadata about AI models and their capabilities
- **GeneratedApplication**: Application instances and their status

**Current Test Data**: 25 AI models, 750 port configurations, 30 applications per model

## 🚀 Quick Start

### 1. Install Dependencies
```bash
python install_dependencies.py
```

### 2. Quick Demo (No Services Required)
```bash
python quick_test_demo.py
```
This runs static analysis only on 2 applications to verify the infrastructure.

### 3. Start Analyzer Services
```bash
python run_all_services.py
```

### 4. Run Comprehensive Tests
```bash
# Quick test (1 app per model, static analyzer only)
python test_real_models.py --quick

# Test specific model and apps
python test_real_models.py --models anthropic_claude-3.7-sonnet --apps 1,2,3

# Test all models with specific analyzers
python test_real_models.py --all-models --analyzers static,ai --parallel 3

# Full comprehensive test (WARNING: Takes 30+ minutes)
python test_real_models.py --all-models --parallel 2
```

## 📋 Available Models (Examples)

From database query, here are some available models:
- `anthropic_claude-3.7-sonnet` (30 apps, ports 9051-9080/6051-6080)
- `deepseek_deepseek-chat` (30 apps, ports 9081-9110/6081-6110) 
- `google_gemini-1.5-pro-002` (30 apps, ports 9111-9140/6111-6140)
- `openai_gpt-4o` (30 apps, ports 9141-9170/6141-6170)
- And 21 more models...

Each model has 30 generated applications in `misc/models/{model_name}/app{1-30}/` with:
- `backend/` - Python Flask applications
- `frontend/` - React/HTML/CSS applications  
- `docker-compose.yml` - Container orchestration

## 🔍 Test Results and Reports

### Console Output
Real-time progress with emoji indicators:
```
🚀 Starting tests on 6 applications with 4 analyzers
📋 Analyzers: static, dynamic, performance, ai
⚡ Parallel workers: 2

📊 Overall Results:
   Total Tests: 24
   Successful: 20 (83.3%)
   Failed: 4
   Models Tested: 3
   Applications Tested: 6
   Total Issues Found: 47

🔍 Analyzer Performance:
   Static Analyzer:
     Tests: 6, Success: 6 (100.0%)
     Issues Found: 23, Avg Duration: 15.2s
```

### JSON Reports
Detailed reports saved as `analyzer_test_report_YYYYMMDD_HHMMSS.json`:
```json
{
  "summary": {
    "total_tests": 24,
    "successful_tests": 20,
    "success_rate": 0.833,
    "total_issues_found": 47
  },
  "analyzer_statistics": {
    "static": {
      "total_tests": 6,
      "successful": 6,
      "total_issues_found": 23
    }
  },
  "test_details": [...]
}
```

## 🛠 Command Line Options

```bash
# Model Selection
--models MODEL1,MODEL2          # Test specific models
--all-models                    # Test all available models
--apps 1,2,3                   # Test specific app numbers
--max-apps N                   # Limit apps per model

# Analyzer Selection  
--analyzers static,dynamic,ai   # Choose which analyzers to test
--quick                        # Quick mode (1 app, static only)

# Execution Control
--parallel N                   # Number of parallel tests (default: 2)
--db-path PATH                 # Database file path
--output FILENAME              # Custom output file name
```

## 📁 File Structure

```
analyzer/
├── test_real_models.py         # Main comprehensive testing script
├── quick_test_demo.py          # Simple demonstration script  
├── install_dependencies.py     # Dependency installer
├── run_all_services.py         # Service orchestration script
├── services/                   # Individual analyzer services
│   ├── static_analyzer/        # Bandit, Pylint, ESLint analysis
│   ├── dynamic_analyzer/       # OWASP ZAP security scanning
│   ├── performance_tester/     # Locust load testing
│   └── ai_analyzer/           # OpenRouter AI analysis
└── README.md                   # This file
```

## 🔧 Architecture

### Test Flow
1. **Discovery**: Query database for model port configurations
2. **Validation**: Check model directories and application structure
3. **Analysis**: Send WebSocket requests to analyzer services
4. **Monitoring**: Track progress and collect results
5. **Reporting**: Generate comprehensive JSON reports and console summaries

### Database Integration
```python
# Example: Get port configurations
with get_session() as session:
    ports = session.query(PortConfiguration).filter_by(
        model='anthropic_claude-3.7-sonnet'
    ).all()
    
    for port in ports:
        app_url = f"http://localhost:{port.frontend_port}"
        # Test application at this URL
```

### WebSocket Communication
```python
# Example: Static analysis request
request = {
    "type": "analysis_request",
    "data": {
        "analysis_type": "static",
        "source_path": "/path/to/app",
        "tools": ["bandit", "pylint", "eslint"]
    }
}
```

## ⚠️ Requirements & Limitations

### Service Dependencies
- **Static Analyzer**: Python packages (bandit, pylint), Node.js packages (eslint)
- **Dynamic Analyzer**: OWASP ZAP proxy, requires running applications
- **Performance Tester**: Locust, requires accessible application endpoints
- **AI Analyzer**: OpenRouter API key, internet connection

### System Requirements
- **Memory**: 4GB+ RAM (parallel testing can be memory intensive)
- **Network**: Localhost connectivity on ports 6051-6200, 8001-8004, 9051-9200
- **Storage**: 100MB+ for test reports and logs
- **Time**: Full test suite takes 30+ minutes

### Known Limitations
- Dynamic analysis requires applications to be running (not implemented in this version)
- Performance testing simulates load but doesn't start actual application containers
- AI analysis requires valid OpenRouter API configuration
- Some models may have malformed applications that cause test failures

## 🐛 Troubleshooting

### Common Issues

**Database Not Found**
```bash
❌ Database file not found: ../src/data/thesis_app.db
```
Solution: Run the main Flask application first to create the database.

**Service Connection Failed**
```bash
❌ Cannot connect to Static Analyzer at ws://localhost:8001
```
Solution: Start analyzer services with `python run_all_services.py`

**No Models Found**
```bash
❌ No applications found for testing
```
Solution: Check that `misc/models/` directory exists and contains model folders.

**WebSocket Import Error**
```bash
⚠️ websockets library not installed
```
Solution: Run `python install_dependencies.py`

### Debug Mode
Enable verbose logging:
```bash
export PYTHONPATH=. 
python -c "import logging; logging.basicConfig(level=logging.DEBUG)"
python test_real_models.py --quick
```

## 📈 Performance Expectations

### Timing Estimates
- **Static Analysis**: 10-30 seconds per application
- **Dynamic Analysis**: 60-180 seconds per application (when implemented)
- **Performance Testing**: 30-90 seconds per application
- **AI Analysis**: 30-120 seconds per application (depends on API speed)

### Resource Usage
- **CPU**: Moderate usage during analysis, high during parallel execution
- **Memory**: ~100MB per analyzer service, ~50MB per test
- **Network**: Local WebSocket traffic, external API calls for AI analysis
- **Disk**: Log files and JSON reports grow with test volume

## 🎯 Future Enhancements

1. **Container Integration**: Automatically start/stop application containers for dynamic testing
2. **Real-time Dashboard**: Web interface for monitoring test progress
3. **Comparative Analysis**: Compare analyzer results across different AI models
4. **Automated Scheduling**: Cron-based regular testing of model updates
5. **Custom Analyzers**: Plugin system for adding new analysis types
6. **Performance Benchmarking**: Historical performance tracking and trends

## 📞 Support

For issues or questions:
1. Check the troubleshooting section above
2. Review log files in `logs/` directory
3. Examine JSON reports for detailed error information
4. Use `--quick` mode to isolate issues
5. Test individual analyzer services separately
