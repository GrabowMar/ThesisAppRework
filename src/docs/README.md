# ThesisAppRework - AI Model Analyzer with Celery Integration

A comprehensive Flask-based web application for researching and testing AI models with asynchronous task processing using Celery. The system integrates with containerized analyzer infrastructure to provide scalable analysis capabilities.

## 🚀 Key Features

- **Asynchronous Task Processing**: Celery-powered task queue with Redis backend
- **Multi-Queue Architecture**: Specialized queues for different analysis types
- **Containerized Analyzers**: Integration with Docker-based analysis services
- **Real-time Task Monitoring**: WebSocket support for live task updates
- **Batch Processing**: Support for bulk analysis operations
- **Health Monitoring**: Comprehensive health checks for all services
- **Database-First**: All data operations use SQLAlchemy models, not JSON files
- **HTMX Frontend**: Responsive UI with HTML fragments, not JSON APIs

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Flask Web     │    │   Celery Tasks  │    │   Analyzer      │
│   Application   │◄──►│   (Redis Queue) │◄──►│   Services      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   SQLAlchemy    │    │   Task Manager  │    │   Docker        │
│   Database      │    │   Service       │    │   Containers    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 📋 Prerequisites

- Python 3.8+
- Redis Server 6.0+
- Docker (for analyzer services)
- SQLite (default) or PostgreSQL

## 🔧 Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd ThesisAppRework/src2
   ```

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Redis** (if not already installed):
   
   **Ubuntu/Debian**:
   ```bash
   sudo apt update
   sudo apt install redis-server
   ```
   
   **macOS**:
   ```bash
   brew install redis
   ```
   
   **Windows**:
   - Download Redis from: https://redis.io/download
   - Or use WSL with Ubuntu instructions

## 🚀 Quick Start

### Option 1: Using Startup Scripts

**Linux/macOS**:
```bash
# Start all services (Flask, Celery, Redis, Analyzers)
bash start.sh start

# Check status
bash start.sh status

# Stop all services
bash start.sh stop
```

**Windows PowerShell**:
```powershell
# Start all services
.\start.ps1 start

# Check status
.\start.ps1 status

# Stop all services
.\start.ps1 stop
```

### Option 2: Manual Start

1. **Start Redis**:
   ```bash
   redis-server
   ```

2. **Start Celery Worker**:
   ```bash
   celery -A app.tasks worker --loglevel=info --concurrency=4
   ```

3. **Start Celery Beat** (for scheduled tasks):
   ```bash
   celery -A app.tasks beat --loglevel=info
   ```

4. **Start Flask Application**:
   ```bash
   python main.py
   ```

5. **Start Analyzer Services** (optional):
   ```bash
   cd ../analyzer
   python analyzer_manager.py start
   ```

## 📊 Task Types

The system supports multiple analysis task types:

### 1. Security Analysis
- Bandit security scanning
- Safety dependency checks
- PyLint code analysis
- ESLint JavaScript analysis

### 2. Performance Testing
- Locust-based load testing
- Response time analysis
- Throughput measurements
- Resource utilization monitoring

### 3. Static Analysis
- Code quality assessment
- Style guide compliance
- Complexity analysis
- Dependency analysis

### 4. AI Analysis
- OpenRouter-based code analysis
- Architecture review
- Best practices validation
- Security vulnerability detection

### 5. Batch Analysis
- Bulk processing capabilities
- Multiple model comparison
- Comprehensive reporting
- Automated scheduling

## 🌐 API Endpoints

### Health Check
```bash
GET /health
```

### Task Management
```bash
# Get active tasks status
GET /api/tasks/status

# Get task execution history
GET /api/tasks/history?limit=50
```

### Analyzer Services
```bash
# Get analyzer services status
GET /api/analyzer/status

# Start analyzer services
POST /api/analyzer/start

# Stop analyzer services
POST /api/analyzer/stop

# Restart analyzer services
POST /api/analyzer/restart
```

## Project Structure

```
src2/
├── app/
│   ├── factory.py           # Flask application factory
│   ├── models.py            # Database models (SQLAlchemy)
│   ├── routes.py            # HTTP route handlers (HTMX endpoints)
│   ├── tasks.py             # Celery tasks
│   └── services/
│       ├── task_manager.py      # Task orchestration
│       └── analyzer_integration.py  # Analyzer bridge
├── config/
│   └── celery_config.py     # Celery configuration
├── main.py                  # Application entry point
├── worker.py                # Celery worker entry point
├── requirements.txt         # Python dependencies
├── start.sh                 # Linux/macOS startup script
├── start.ps1                # Windows startup script
└── README.md               # This file
```
   ```

2. **Access the web interface**:
   - Main dashboard: http://localhost:5000
   - Models overview: http://localhost:5000/models
   - App testing: http://localhost:5000/app/{model}/{app_num}

3. **Start analyzer services** (optional):
   ```bash
   cd ../analyzer
   python analyzer_manager.py start
   ```

## Development Notes

- **Database First**: Always use SQLAlchemy models for data operations
- **Read-Only External Data**: Never modify files in `misc/` or `analyzer/` directories
- **HTMX Patterns**: Return HTML fragments from routes, not JSON
- **Service Layer**: Use dependency injection via ServiceLocator pattern
- **Error Handling**: Graceful degradation when external services are unavailable

## Architecture Principles

1. **Separation of Concerns**: Models, routes, services, and utilities are clearly separated
2. **Dependency Injection**: Services are managed through a centralized ServiceLocator
3. **Database Abstraction**: All data access goes through SQLAlchemy models
4. **External Integration**: Clean interfaces to analyzer services and model data
5. **Testing**: Comprehensive unit and integration test coverage
