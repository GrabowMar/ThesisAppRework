# WebSocket-Based Testing Infrastructure (Analyzer)

## Overview
A modern, real-time testing infrastructure built entirely on WebSocket communication for analyzing AI-generated applications. This replaces the legacy REST-based approach with bidirectional, event-driven communication.

## Key Features
- **Real-time Progress Updates**: Live streaming of analysis progress
- **Event-Driven Architecture**: Asynchronous message-based communication
- **Microservice Design**: Independent, containerized analysis services
- **Modern Security**: Non-root containers, health checks, and resource limits
- **Scalable**: Built with asyncio and proper resource management

## Architecture Components

### Core Gateway (`websocket_gateway.py`)
- Central WebSocket hub for all communication
- Connection management and message routing
- Service discovery and health monitoring
- Authentication and rate limiting

### Analysis Services
- **Security Analyzer** - Bandit, Safety, Pylint integration
- **Performance Tester** - Locust-based load testing
- **Dependency Scanner** - npm audit, pip-audit
- **Code Quality** - ESLint, Flake8, Black
- **AI Analyzer** - OpenRouter integration for intelligent analysis

### Shared Components (`shared/`)
- `protocol.py` - WebSocket message protocol definitions
- `client.py` - Client library for easy integration
- Common data models and utilities

## Quick Start

### Prerequisites
- Docker Desktop with Docker Compose
- Python 3.12+ (for local testing)

### 1. Setup and Start Services

```bash
# Navigate to analyzer directory
cd analyzer

# Run complete setup (creates test data, builds, and starts services)
python setup.py all

# Or run individual steps:
python setup.py setup    # Just setup infrastructure
python setup.py test     # Just run tests
python setup.py logs     # View service logs
python setup.py cleanup  # Clean up everything
```

### 2. Manual Docker Commands

```bash
# Build and start services
docker compose build
docker compose up -d

# Check service status
docker compose ps

# View logs
docker compose logs -f

# Stop services
docker compose down -v
```

### 3. Test the Infrastructure

```bash
# Run the test client
python test_client.py
```

## Technology Stack

### WebSocket Infrastructure
- **websockets** library with asyncio for high-performance communication
- Real-time bidirectional messaging
- Automatic reconnection and health monitoring

### Security Tools
- **Bandit** - Python security linter
- **Safety** - Python dependency vulnerability scanner
- **Pylint** - Code quality and security analysis

### Container Technology
- **Docker** with modern 2025 best practices
- Multi-stage builds for minimal image sizes
- Non-root users for security
- Health checks and resource limits

### Monitoring
- **Prometheus** - Metrics collection
- **Grafana** - Visualization dashboard
- **Redis** - Caching and task queues

## Modern Docker Practices (2025)

### ✅ What We Implement
- **No `version:` field** in docker-compose.yml
- **Health checks** for all services
- **Non-root users** (1000:1000) for security
- **Multi-stage builds** for minimal images
- **Resource limits** and reservations
- **.dockerignore** for optimized builds
- **Restart policies** for reliability

### 📊 Service Endpoints
- **WebSocket Gateway**: `ws://localhost:8765`
- **Prometheus**: `http://localhost:9090`
- **Grafana**: `http://localhost:3000` (admin/admin)

## API Usage

### Python Client Example

```python
import asyncio
from shared.client import AnalyzerClient
from shared.protocol import SecurityAnalysisRequest, AnalysisType

async def analyze_code():
    # Create analysis request
    request = SecurityAnalysisRequest(
        model="gpt-4",
        app_number=1,
        analysis_type=AnalysisType.SECURITY_PYTHON,
        source_path="path/to/code",
        tools=['bandit', 'safety', 'pylint']
    )
    
    # Analyze with progress updates
    async with AnalyzerClient("ws://localhost:8765") as client:
        # Register progress handler
        async def on_progress(message):
            print(f"Progress: {message.data['progress']:.1%}")
        
        client.register_handler(MessageType.PROGRESS_UPDATE, on_progress)
        
        # Request analysis
        result = await client.request_analysis(request)
        print(f"Found {result.data['total_issues']} issues")

# Run the analysis
asyncio.run(analyze_code())
```

### WebSocket Message Protocol

```json
{
  "type": "analysis_request|analysis_result|progress_update",
  "id": "unique_message_id",
  "service": "security_analyzer|performance_tester|...",
  "data": { /* service-specific payload */ },
  "timestamp": "2025-08-08T12:00:00Z",
  "client_id": "requesting_client_identifier",
  "correlation_id": "request_correlation_id"
}
```

## Development

### Adding New Analysis Services

1. Create service directory in `services/`
2. Implement WebSocket service following the pattern
3. Add to `docker-compose.yml`
4. Update shared protocol if needed

### Service Structure
```
services/my-analyzer/
├── Dockerfile
├── requirements.txt
├── main.py
└── .dockerignore
```

### WebSocket Service Template

```python
class MyAnalyzer:
    async def handle_analysis_request(self, message: WebSocketMessage):
        # 1. Parse request
        # 2. Send progress updates
        # 3. Perform analysis
        # 4. Send results
        pass
    
    async def send_progress_update(self, analysis_id, stage, progress, message):
        progress_msg = create_progress_update_message(
            analysis_id, stage, progress, message
        )
        await self.websocket.send(progress_msg.to_json())
```

## Monitoring and Debugging

### View Logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f security-analyzer

# Gateway only
docker compose logs -f gateway
```

### Check Service Health
```bash
# Service status
docker compose ps

# Health check status
docker inspect analyzer-gateway-1 | grep Health -A 10
```

### Prometheus Metrics
Visit `http://localhost:9090` and query:
- `up` - Service availability
- `websocket_connections` - Active connections
- `analysis_duration_seconds` - Analysis performance

### Grafana Dashboards
Visit `http://localhost:3000` (admin/admin) for:
- Service health dashboard
- Analysis performance metrics
- WebSocket connection monitoring

## Troubleshooting

### Common Issues

**Services won't start:**
```bash
# Check Docker status
docker --version
docker compose --version

# Check ports
netstat -an | grep -E "8765|9090|3000"

# Rebuild images
docker compose build --no-cache
```

**WebSocket connection fails:**
```bash
# Check gateway logs
docker compose logs gateway

# Test connection manually
python -c "import asyncio, websockets; asyncio.run(websockets.connect('ws://localhost:8765'))"
```

**Analysis fails:**
```bash
# Check service logs
docker compose logs security-analyzer

# Verify test data exists
ls -la ../misc/models/test/app1/
```

### Performance Tuning

**Memory limits:**
```yaml
deploy:
  resources:
    limits:
      memory: 2G      # Increase for large codebases
      cpus: '1.0'     # Adjust based on CPU cores
```

**WebSocket settings:**
```python
# In websocket_gateway.py
websockets.serve(
    handler,
    host, port,
    max_size=2*1024*1024,  # 2MB message limit
    max_queue=64           # Queue size
)
```

## Security Considerations

### Container Security
- All services run as non-root users (1000:1000)
- Read-only file systems where possible
- Resource limits prevent DoS attacks
- Health checks enable automatic recovery

### Network Security
- Services communicate over internal Docker network
- Only necessary ports exposed to host
- No hardcoded credentials in images

### Data Security
- Analysis results stored in named volumes
- Source code mounted read-only
- Sensitive data handled via environment variables

## Future Enhancements

### Planned Features
- [ ] Kubernetes deployment manifests
- [ ] Advanced batch processing
- [ ] Machine learning-based security analysis
- [ ] Integration with CI/CD pipelines
- [ ] Custom analysis rule engine

### Performance Improvements
- [ ] Result caching with Redis
- [ ] Parallel analysis execution
- [ ] Load balancing across service instances
- [ ] Streaming large file analysis

---

## Contributing

1. Fork the repository
2. Create feature branch
3. Follow Docker and Python best practices
4. Add tests for new functionality
5. Update documentation
6. Submit pull request

## License

This project is part of the ThesisAppRework system for AI model analysis.
