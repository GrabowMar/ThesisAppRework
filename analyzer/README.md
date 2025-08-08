# Analyzer Infrastructure

Containerized microservices for comprehensive application analysis including security, performance, and AI-powered requirements testing.

## Overview

This infrastructure provides four specialized analyzer services:

1. **Static Analyzer** - Security and quality analysis using multiple tools
2. **Dynamic Analyzer** - OWASP ZAP-based security scanning  
3. **Performance Tester** - Locust-based load testing
4. **AI Analyzer** - OpenRouter-powered requirements and code analysis

All services communicate via WebSocket protocols and can analyze applications stored in the `misc/models/` directory.

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web App       │    │   Gateway       │    │   Services      │
│   (src/)        │───▶│   (WebSocket)   │───▶│   Container     │
│                 │    │   Port 8765     │    │   Network       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                               │
                      ┌────────────────────────┼────────────────────────┐
                      │                        │                        │
            ┌─────────▼──┐            ┌───────▼───┐            ┌───────▼───┐
            │  Static    │            │  Dynamic  │            │Performance│
            │ Analyzer   │            │ Analyzer  │            │  Tester   │
            │ Port 8001  │            │Port 8002  │            │Port 8003  │
            └────────────┘            └───────────┘            └───────────┘
                      │                        │                        │
                      │                ┌───────▼───┐                    │
                      │                │    AI     │                    │
                      │                │ Analyzer  │                    │
                      │                │Port 8004  │                    │
                      │                └───────────┘                    │
                      │                        │                        │
                      └────────────────────────┼────────────────────────┘
                                               │
                                    ┌─────────▼──┐
                                    │   Redis    │
                                    │   Cache    │
                                    └────────────┘
```

## Services

### Static Analyzer (Port 8001)
**Purpose**: Frontend and backend security/quality analysis  
**Tools**: Bandit, Safety, Pylint, ESLint, Stylelint  
**Languages**: Python, JavaScript/TypeScript, CSS, HTML

**Features**:
- Multi-language static analysis
- Security vulnerability detection
- Code quality assessment
- Dependency security scanning
- Comprehensive reporting

### Dynamic Analyzer (Port 8002)
**Purpose**: Runtime security testing  
**Tools**: OWASP ZAP v2.14.0  
**Target**: Running web applications

**Features**:
- Spider crawling for endpoint discovery
- Active security scanning
- Vulnerability assessment
- OWASP Top 10 coverage
- Dynamic penetration testing

### Performance Tester (Port 8003)
**Purpose**: Load testing and performance analysis  
**Tools**: Locust framework  
**Scenarios**: Basic load, stress test, spike test, endurance test

**Features**:
- Multiple load testing scenarios
- Real-time performance monitoring
- Bottleneck identification
- Scalability assessment
- Performance score calculation

### AI Analyzer (Port 8004)
**Purpose**: AI-powered code and requirements analysis  
**Tools**: OpenRouter API integration  
**Analysis Types**: Requirements check, code review, security audit, architecture review, documentation check

**Features**:
- Requirements compliance verification
- AI-powered code review
- Security audit with AI insights
- Architecture pattern analysis
- Documentation completeness check

## Quick Start

### Prerequisites
- Docker and Docker Compose
- OpenRouter API key (for AI analysis)
- Windows environment (tested on Windows 11)

### Environment Setup

1. **Clone and navigate to analyzer directory**:
   ```powershell
   cd analyzer/
   ```

2. **Set up environment variables** (create `.env` file):
   ```bash
   OPENROUTER_API_KEY=your_openrouter_api_key_here
   LOG_LEVEL=INFO
   ```

3. **Build and start services**:
   ```powershell
   docker-compose up --build
   ```

4. **Verify services are running**:
   ```powershell
   # Check all services
   docker-compose ps
   
   # Test individual services
   docker-compose exec static-analyzer python health_check.py
   docker-compose exec dynamic-analyzer python health_check.py
   docker-compose exec performance-tester python health_check.py
   docker-compose exec ai-analyzer python health_check.py
   ```

### Testing the Services

**Static Analysis Example**:
```python
import asyncio
import websockets
import json

async def test_static_analysis():
    uri = "ws://localhost:8001"
    async with websockets.connect(uri) as websocket:
        request = {
            "type": "analysis_request",
            "data": {
                "analysis_type": "static",
                "source_path": "/app/sources/anthropic_claude-3.7-sonnet/app1",
                "tools": ["bandit", "pylint", "eslint"]
            }
        }
        await websocket.send(json.dumps(request))
        response = await websocket.recv()
        print("Static Analysis Result:", json.loads(response))

asyncio.run(test_static_analysis())
```

**Performance Testing Example**:
```python
import asyncio
import websockets
import json

async def test_performance():
    uri = "ws://localhost:8003"
    async with websockets.connect(uri) as websocket:
        request = {
            "type": "analysis_request", 
            "data": {
                "analysis_type": "performance",
                "target_url": "http://localhost:3000",
                "scenario": "stress_test",
                "duration": 60,
                "users": 10
            }
        }
        await websocket.send(json.dumps(request))
        response = await websocket.recv()
        print("Performance Test Result:", json.loads(response))

asyncio.run(test_performance())
```

## Configuration

### Service Ports
- **Gateway**: 8765 (WebSocket coordination)
- **Static Analyzer**: 8001
- **Dynamic Analyzer**: 8002 (ZAP on 8090 internally)
- **Performance Tester**: 8003
- **AI Analyzer**: 8004
- **Redis**: 6379 (internal)

### Volume Mounts
- **Source Code**: `../misc/models:/app/sources:ro` (read-only)
- **Results**: Individual volumes per service
- **Redis Data**: Persistent cache storage

### Resource Limits
- **Static/AI Analyzers**: 1-2GB RAM, 0.5-1.0 CPU
- **Dynamic Analyzer**: 2GB RAM, 1.0 CPU (ZAP requirements)
- **Performance Tester**: 2GB RAM, 1.0 CPU
- **Redis**: 256MB RAM, 0.1 CPU

## API Protocol

All services use a unified WebSocket protocol with the following message types:

### Request Format
```json
{
  "type": "analysis_request",
  "id": "unique_request_id",
  "timestamp": "2025-01-27T10:00:00Z",
  "data": {
    "analysis_type": "static|dynamic|performance|ai",
    "source_path": "/app/sources/model/app1",
    "configuration": {...}
  }
}
```

### Response Format
```json
{
  "type": "analysis_result",
  "id": "response_id",
  "correlation_id": "request_id",
  "timestamp": "2025-01-27T10:05:00Z",
  "data": {
    "analysis_id": "uuid",
    "status": "completed|failed|in_progress",
    "issues": [...],
    "summary": {...},
    "metadata": {...}
  }
}
```

### Progress Updates
```json
{
  "type": "progress_update",
  "data": {
    "analysis_id": "uuid",
    "stage": "analyzing",
    "progress": 0.75,
    "message": "Running security scan..."
  }
}
```

## Integration with Main Application

The analyzer infrastructure integrates with the main Flask application in `src/`:

1. **Service Discovery**: Use `ServiceLocator` to access analyzer services
2. **Database Storage**: Results stored in SQLAlchemy models
3. **Web Interface**: HTMX endpoints for triggering analysis
4. **Configuration**: Dynamic configuration from database

### Example Integration
```python
from src.service_manager import ServiceLocator

# Get analyzer service
analyzer_service = ServiceLocator.get_analyzer_service()

# Start analysis
result = await analyzer_service.analyze_application(
    model_slug="anthropic_claude-3.7-sonnet",
    app_number=1,
    analysis_types=["static", "performance", "ai"]
)
```

## Monitoring and Health Checks

### Health Check Endpoints
Each service provides health check functionality:
```bash
# Individual service health
docker-compose exec static-analyzer python health_check.py
docker-compose exec dynamic-analyzer python health_check.py
docker-compose exec performance-tester python health_check.py
docker-compose exec ai-analyzer python health_check.py
```

### Docker Health Checks
Services include Docker health checks with automatic restart on failure:
```yaml
healthcheck:
  test: ["CMD", "python", "health_check.py"]
  interval: 30s
  timeout: 5s
  retries: 3
  start_period: 15s
```

### Logs
```bash
# View all service logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f static-analyzer
docker-compose logs -f dynamic-analyzer
docker-compose logs -f performance-tester
docker-compose logs -f ai-analyzer
```

## Troubleshooting

### Common Issues

**1. Service Won't Start**
```bash
# Check service status
docker-compose ps

# View logs for errors
docker-compose logs service-name

# Restart specific service
docker-compose restart service-name
```

**2. WebSocket Connection Issues**
```bash
# Check if service is listening
docker-compose exec service-name netstat -tulpn | grep 800X

# Test WebSocket connectivity
docker-compose exec service-name python -c "import websockets; print('WebSocket library available')"
```

**3. ZAP/Dynamic Analyzer Issues**
```bash
# Check ZAP daemon status
docker-compose exec dynamic-analyzer ps aux | grep zap

# Check ZAP logs
docker-compose exec dynamic-analyzer cat /zap/data/zap.log
```

**4. AI Analyzer Issues**
```bash
# Check OpenRouter API key
docker-compose exec ai-analyzer env | grep OPENROUTER

# Test API connectivity
docker-compose exec ai-analyzer python -c "import requests; print(requests.get('https://openrouter.ai/api/v1/models').status_code)"
```

### Performance Optimization

**Resource Scaling**:
```yaml
# Increase resources for heavy workloads
deploy:
  resources:
    limits:
      memory: 4G
      cpus: '2.0'
```

**Parallel Analysis**:
- Use multiple instances of the same service
- Configure load balancing in the gateway
- Scale horizontally with Docker Swarm

### Development and Testing

**Running Individual Services**:
```bash
# Build specific service
docker-compose build static-analyzer

# Run service in isolation
docker-compose up static-analyzer redis

# Access service shell
docker-compose exec static-analyzer /bin/bash
```

**Testing Protocol Changes**:
```bash
# Update shared protocol
cd shared/
# Make changes to protocol.py

# Rebuild affected services
docker-compose build static-analyzer dynamic-analyzer performance-tester ai-analyzer
```

## Contributing

### Adding New Analyzers

1. **Create service directory**: `services/your-analyzer/`
2. **Implement Dockerfile**: Follow existing patterns
3. **Create main.py**: Implement WebSocket handler
4. **Add requirements.txt**: List dependencies
5. **Create health_check.py**: Implement health check
6. **Update docker-compose.yml**: Add service configuration
7. **Update shared protocol**: Add new message types if needed

### Service Template Structure
```
services/your-analyzer/
├── Dockerfile
├── main.py
├── requirements.txt
├── health_check.py
└── README.md
```

## Security Considerations

- **Non-root users**: All containers run as non-root
- **Read-only mounts**: Source code mounted read-only
- **Network isolation**: Services in isolated Docker network
- **Resource limits**: Prevent resource exhaustion
- **API key security**: Environment variables for secrets
- **Health monitoring**: Automatic restart on failure

## Modern Docker Practices (2025)

### ✅ What We Implement
- **No `version:` field** in docker-compose.yml
- **Health checks** for all services
- **Non-root users** (1000:1000) for security
- **Multi-stage builds** for minimal images
- **Resource limits** and reservations
- **.dockerignore** for optimized builds
- **Restart policies** for reliability

## License

This analyzer infrastructure is part of the ThesisAppRework project. Please refer to the main project license for usage terms.
