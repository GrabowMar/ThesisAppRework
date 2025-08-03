# Containerized Batch Analysis System

## Overview

The new containerized batch analysis system provides a completely redesigned approach to running analysis tools for the thesis research platform. Instead of running tools directly on the host system, all analysis is performed within a dedicated Docker container with pre-installed tools.

## Architecture

### Components

1. **Analysis Container** (`analysis-container/`)
   - Pre-built Docker image with all analysis tools
   - FastAPI server for receiving analysis requests
   - Isolated execution environment
   - Standardized tool configurations

2. **Containerized Batch Service** (`src/containerized_batch_service.py`)
   - Orchestrates analysis jobs
   - Manages communication with analysis container
   - Handles job queueing and progress tracking
   - Aggregates results from multiple analyses

3. **New API Routes** (`src/containerized_batch_routes.py`)
   - RESTful API endpoints under `/api/v2/batch/`
   - Web interface for job management
   - Real-time status updates

## Features

### ✅ Improvements Over Previous System

- **Better Isolation**: Tools run in containerized environment
- **Consistency**: Same environment across all analyses
- **Scalability**: Can run multiple analysis containers
- **Resource Management**: Better control over CPU/memory usage
- **Tool Versioning**: Fixed tool versions in container
- **Error Handling**: Improved error isolation and reporting
- **Async Processing**: Non-blocking job execution

### 🔧 Available Analysis Tools

#### Security Tools
- **Bandit**: Python security analysis
- **Safety**: Dependency vulnerability scanning
- **Semgrep**: Static analysis security testing
- **ESLint**: JavaScript/TypeScript security linting
- **Retire.js**: JavaScript vulnerability detection
- **Snyk**: Comprehensive vulnerability scanning
- **TruffleHog**: Secret detection

#### Performance Tools
- **Locust**: Load testing and performance analysis
- **Lighthouse**: Web performance auditing

#### Code Quality Tools
- **Flake8**: Python code style checking
- **Pylint**: Python code analysis
- **MyPy**: Python static type checking
- **SonarQube**: Code quality analysis

#### Container Security Tools
- **Docker Scan**: Container vulnerability scanning
- **Trivy**: Container image security scanning

## Quick Start

### 1. Start the Analysis Container

```powershell
# Windows PowerShell
.\start-analysis-container.ps1
```

```bash
# Linux/macOS
./start-analysis-container.sh
```

### 2. Verify Container Health

```powershell
Invoke-WebRequest http://localhost:8080/health
```

### 3. Create and Run Analysis Job

```powershell
# Create a batch job
$jobConfig = @{
    name = "Security Analysis Test"
    description = "Test security analysis on selected models"
    models = @("anthropic_claude-3.7-sonnet")
    app_range = @{start = 1; end = 5}
    analysis_types = @("security_backend", "security_frontend")
    tools = @("bandit", "safety", "eslint")
    parallel_jobs = 2
} | ConvertTo-Json

$response = Invoke-WebRequest -Uri "http://localhost:5000/api/v2/batch/jobs" -Method POST -Body $jobConfig -ContentType "application/json"
$jobId = ($response.Content | ConvertFrom-Json).job_id

# Start the job
Invoke-WebRequest -Uri "http://localhost:5000/api/v2/batch/jobs/$jobId/start" -Method POST

# Check job status
Invoke-WebRequest -Uri "http://localhost:5000/api/v2/batch/jobs/$jobId"
```

## API Documentation

### Health and Tools

- `GET /api/v2/batch/health` - Check system health
- `GET /api/v2/batch/tools` - List available tools

### Job Management

- `POST /api/v2/batch/jobs` - Create new job
- `GET /api/v2/batch/jobs` - List all jobs
- `GET /api/v2/batch/jobs/{id}` - Get job status
- `POST /api/v2/batch/jobs/{id}/start` - Start job
- `POST /api/v2/batch/jobs/{id}/stop` - Stop job
- `GET /api/v2/batch/jobs/{id}/results` - Get job results

### Web Interface

- `GET /api/v2/batch/dashboard` - Job management dashboard
- `GET /api/v2/batch/create` - Create job form
- `GET /api/v2/batch/jobs/{id}/view` - View job details

## Configuration

### Job Configuration Schema

```json
{
  "name": "Job Name",
  "description": "Optional description",
  "priority": "normal|high|low",
  "models": ["model1", "model2"],
  "app_range": {"start": 1, "end": 30},
  "analysis_types": ["security_backend", "performance"],
  "tools": ["bandit", "safety", "locust"],
  "container_options": {
    "timeout": 3600,
    "memory_limit": "2G"
  },
  "parallel_jobs": 4
}
```

### Analysis Types

- `security_backend` - Backend security analysis
- `security_frontend` - Frontend security analysis  
- `security_combined` - Both backend and frontend security
- `performance` - Performance testing
- `code_quality` - Code quality analysis
- `container_scan` - Container security scanning

## File Structure

```
analysis-container/
├── Dockerfile                 # Container image definition
├── requirements.txt          # Python dependencies
├── api/
│   ├── server.py            # FastAPI analysis server
│   ├── models.py            # Pydantic models
│   ├── analyzers.py         # Tool implementations
│   └── utils.py             # Utility functions
└── config/
    ├── bandit.json          # Tool configurations
    ├── safety.json
    ├── semgrep.json
    └── eslint.json

src/
├── containerized_batch_service.py    # Main service
├── containerized_batch_routes.py     # API routes
└── batch_service.py                  # Legacy compatibility

docker-compose.analysis.yml           # Container orchestration
start-analysis-container.ps1          # Windows startup script
start-analysis-container.sh           # Unix startup script
```

## Migration from Legacy System

### Code Changes Required

1. **Import Changes**
   ```python
   # Old
   from .batch_service import BatchService
   
   # New
   from .containerized_batch_service import ContainerizedBatchService
   ```

2. **Route Registration**
   ```python
   # Add to app.py
   from .containerized_batch_routes import register_batch_routes
   register_batch_routes(app)
   ```

3. **Job Creation**
   ```python
   # Old format still supported, but new format recommended
   service = get_containerized_batch_service()
   job_id = service.create_batch_job(config_dict)
   ```

### Breaking Changes

- API endpoints moved from `/api/batch/` to `/api/v2/batch/`
- Job execution is now asynchronous by default
- Tool configuration format changed
- Results structure updated

## Troubleshooting

### Container Issues

1. **Container won't start**
   ```powershell
   # Check Docker status
   docker info
   
   # View container logs
   docker-compose -f docker-compose.analysis.yml logs
   ```

2. **Health check fails**
   ```powershell
   # Check container status
   docker-compose -f docker-compose.analysis.yml ps
   
   # Test network connectivity
   Test-NetConnection localhost -Port 8080
   ```

3. **Analysis jobs fail**
   ```powershell
   # Check analysis container logs
   docker logs thesis-analysis-container
   
   # Verify tools are available
   Invoke-WebRequest http://localhost:8080/tools
   ```

### Performance Tuning

1. **Increase parallel jobs**
   ```json
   {
     "parallel_jobs": 8,
     "container_options": {
       "memory_limit": "4G"
     }
   }
   ```

2. **Tool-specific timeouts**
   ```json
   {
     "container_options": {
       "timeout": 7200,
       "tool_timeouts": {
         "semgrep": 3600,
         "bandit": 1800
       }
     }
   }
   ```

## Development

### Building the Container

```powershell
docker build -t thesis-analysis-container ./analysis-container
```

### Running in Development Mode

```powershell
# Start with live reload
docker-compose -f docker-compose.analysis.yml -f docker-compose.dev.yml up
```

### Adding New Tools

1. Update `analysis-container/Dockerfile` to install the tool
2. Add tool configuration in `analysis-container/config/`
3. Implement analyzer in `analysis-container/api/analyzers.py`
4. Update `ToolType` enum in `analysis-container/api/models.py`

## Security Considerations

- Analysis container runs with limited privileges
- Network isolation between containers
- Volume mounts are read-only where possible
- Sensitive data is not persisted in containers
- Regular security updates for base images

## Performance Metrics

- Analysis throughput: ~10-20 apps/minute depending on tools
- Memory usage: 2-4GB per container
- Storage: ~50MB per analysis result set
- Network: Minimal traffic between main app and container

## Support

For issues or questions:
1. Check container logs: `docker-compose -f docker-compose.analysis.yml logs`
2. Verify API health: `GET /api/v2/batch/health`
3. Review job status: `GET /api/v2/batch/jobs/{id}`
4. Check tool availability: `GET /api/v2/batch/tools`
