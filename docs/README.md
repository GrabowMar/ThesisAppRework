# ThesisApp Documentation

> **AI Model Analysis Platform** - Comprehensive testing and evaluation of AI-generated applications

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-required-blue.svg)](https://docker.com)

---

## 📚 Documentation Map

```mermaid
graph LR
    A[📖 Start Here] --> B[🏗️ Architecture]
    A --> C[🚀 Getting Started]
    B --> D[✨ Features]
    C --> D
    D --> E[📋 Guides]
    E --> F[📖 Reference]
    
    style A fill:#4CAF50
    style B fill:#2196F3
    style C fill:#FF9800
    style D fill:#9C27B0
    style E fill:#00BCD4
    style F fill:#607D8B
```

---

## 🚀 Quick Navigation

### Getting Started
- **[Getting Started Guide](GETTING_STARTED.md)** - Installation, setup, and first steps
- **[Architecture Overview](ARCHITECTURE.md)** - System design and component interaction

### Core Features
- **[Application Generation](features/GENERATION.md)** - AI-powered app generation system
- **[Analysis Pipeline](features/ANALYSIS.md)** - Multi-dimensional analysis tools
- **[Port Management](features/PORT_ALLOCATION.md)** - Automatic port allocation system
- **[Container Orchestration](features/CONTAINERS.md)** - Docker-based app management

### How-To Guides
- **[Generate Applications](guides/GENERATING_APPS.md)** - Step-by-step generation guide
- **[Run Analysis](guides/RUNNING_ANALYSIS.md)** - Execute security, performance, and quality tests
- **[Manage Applications](guides/MANAGING_APPS.md)** - Start, stop, and monitor generated apps
- **[Batch Operations](guides/BATCH_OPERATIONS.md)** - Process multiple apps at once

### Technical Reference
- **[API Reference](reference/API.md)** - REST API endpoints and schemas
- **[Database Schema](reference/DATABASE.md)** - Data models and relationships
- **[Configuration](reference/CONFIGURATION.md)** - Environment variables and settings
- **[CLI Commands](reference/CLI.md)** - Analyzer manager command reference

---

## 🎯 What is ThesisApp?

ThesisApp is a comprehensive platform for **generating, executing, and analyzing AI-generated applications** across multiple dimensions:

```mermaid
graph TB
    subgraph "Generation"
        A[AI Model] --> B[Template System]
        B --> C[Generated App]
    end
    
    subgraph "Execution"
        C --> D[Docker Container]
        D --> E[Running Application]
    end
    
    subgraph "Analysis"
        E --> F[Security Scan]
        E --> G[Performance Test]
        E --> H[Code Quality]
        E --> I[AI Review]
    end
    
    subgraph "Results"
        F --> J[Comprehensive Report]
        G --> J
        H --> J
        I --> J
    end
    
    style A fill:#FF6B6B
    style C fill:#4ECDC4
    style E fill:#95E1D3
    style J fill:#FFA502
```

### Key Capabilities

| Feature | Description |
|---------|-------------|
| 🤖 **Multi-Model Support** | OpenAI, Anthropic, Google, Meta, and more |
| 🛡️ **Security Analysis** | Bandit, Safety, OWASP ZAP, Semgrep |
| ⚡ **Performance Testing** | Locust, Apache Bench, custom load tests |
| 🔍 **Code Quality** | Pylint, Flake8, ESLint, complexity metrics |
| 🧠 **AI Reviews** | Automated code review using LLMs |
| 📦 **Container Management** | Docker orchestration with health monitoring |
| 🔄 **Batch Processing** | Parallel generation and analysis |
| 📊 **Rich Reporting** | Interactive dashboards and exports |

---

## 🏗️ System Architecture

<details>
<summary><b>Click to expand architecture diagram</b></summary>

```mermaid
graph TB
    subgraph "Frontend Layer"
        UI[Web UI<br/>Bootstrap + HTMX]
        WS[WebSocket Client]
    end
    
    subgraph "Application Layer"
        Flask[Flask App<br/>:5000]
        Celery[Celery Workers]
        WSG[WebSocket Gateway<br/>:8765]
    end
    
    subgraph "Analyzer Services"
        Static[Static Analyzer<br/>:2001]
        Dynamic[Dynamic Analyzer<br/>:2002]
        Perf[Performance Tester<br/>:2003]
        AI[AI Analyzer<br/>:2004]
    end
    
    subgraph "Data Layer"
        DB[(SQLite/PostgreSQL)]
        Redis[(Redis Cache)]
        Files[File System<br/>generated/apps]
    end
    
    UI --> Flask
    UI --> WS
    WS --> WSG
    Flask --> Celery
    Flask --> DB
    Celery --> Static
    Celery --> Dynamic
    Celery --> Perf
    Celery --> AI
    Static --> WSG
    Dynamic --> WSG
    Perf --> WSG
    AI --> WSG
    Celery --> Files
    Celery --> Redis
    
    style UI fill:#4CAF50
    style Flask fill:#2196F3
    style Celery fill:#FF9800
    style DB fill:#9C27B0
```

</details>

---

## 📦 Project Structure

```
ThesisAppRework/
├── src/                    # Flask application
│   ├── app/               # Application package
│   │   ├── routes/        # Blueprint routes
│   │   ├── services/      # Business logic
│   │   ├── models/        # Database models
│   │   └── tasks/         # Celery tasks
│   ├── templates/         # Jinja2 templates
│   └── static/            # CSS, JS, assets
├── analyzer/              # Analysis orchestration
│   ├── services/          # Analyzer microservices
│   │   ├── static-analyzer/
│   │   ├── dynamic-analyzer/
│   │   ├── performance-tester/
│   │   └── ai-analyzer/
│   └── shared/            # Shared utilities
├── generated/             # Generated applications
│   └── apps/              # Model apps organized by slug
├── misc/                  # Templates and configs
│   ├── app_templates/     # Generation templates
│   └── code_templates/    # Scaffolding templates
├── results/               # Analysis results
└── docs/                  # Documentation (you are here)
```

---

## 🚦 Quick Start

### Prerequisites

```bash
# Required
✓ Python 3.9+
✓ Docker & Docker Compose
✓ Redis

# Optional
✓ PostgreSQL (production)
```

### Installation

```bash
# 1. Clone and setup
git clone https://github.com/YourOrg/ThesisAppRework.git
cd ThesisAppRework
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 3. Initialize database
cd src && python init_db.py

# 4. Start analyzer services
cd ../analyzer
docker-compose up -d

# 5. Start Flask app
cd ../src
python main.py

# 6. Start Celery worker (separate terminal)
celery -A app.tasks worker --loglevel=info
```

### First Analysis

```bash
# Generate and analyze an app
python analyzer/analyzer_manager.py analyze anthropic_claude-3.5-sonnet 1

# Or use the web interface
# Navigate to http://localhost:5000
```

---

## 📊 Analysis Workflow

```mermaid
sequenceDiagram
    participant User
    participant Flask
    participant Celery
    participant Analyzer
    participant WebSocket
    
    User->>Flask: Request Analysis
    Flask->>Celery: Queue Task
    Flask->>User: Task ID
    
    Celery->>Analyzer: Start Analysis
    
    loop Analysis Progress
        Analyzer->>WebSocket: Progress Update
        WebSocket->>User: Real-time Status
    end
    
    Analyzer->>Celery: Results
    Celery->>Flask: Update Database
    Flask->>User: Complete Notification
```

---

## 🔧 Configuration

### Environment Variables

```bash
# Required
OPENROUTER_API_KEY=sk-...        # AI model access
FLASK_SECRET_KEY=random-string   # Session security

# Optional
DATABASE_URL=sqlite:///app.db    # Database connection
REDIS_URL=redis://localhost:6379 # Cache/queue
ANALYZER_TIMEOUT=300             # Analysis timeout (seconds)
DISABLED_ANALYSIS_MODELS=model1,model2  # Skip specific models
```

See [Configuration Reference](reference/CONFIGURATION.md) for complete details.

---

## 📈 Key Metrics

| Metric | Value |
|--------|-------|
| **Supported Models** | 50+ (OpenAI, Anthropic, Google, Meta, etc.) |
| **Analysis Tools** | 15 (Security, Performance, Quality, AI) |
| **Template Library** | 60+ app templates (30 backend, 30 frontend) |
| **Analyzer Services** | 4 containerized microservices |
| **Test Coverage** | >90% |

---

## 🤝 Contributing

See our [Development Guide](DEVELOPMENT_GUIDE.md) for:
- Development setup
- Code style guidelines
- Testing requirements
- Pull request process

---

## 📝 Recent Updates

<details>
<summary><b>October 2025 - Major Enhancements</b></summary>

- ✅ Multi-tier template system for weak model support
- ✅ Automatic port allocation system
- ✅ Application status caching with Docker sync
- ✅ Enhanced frontend with Tabler components
- ✅ Unified analysis pipeline with 15 tools
- ✅ Real-time WebSocket progress updates

See [CHANGELOG.md](CHANGELOG.md) for complete history.

</details>

---

## 📞 Support & Resources

- **Issues**: [GitHub Issues](https://github.com/YourOrg/ThesisAppRework/issues)
- **Discussions**: [GitHub Discussions](https://github.com/YourOrg/ThesisAppRework/discussions)
- **Documentation**: You're reading it! 📖

---

## 📄 License

MIT License - see [LICENSE](../LICENSE) for details.

---

**Last Updated**: October 2025  
**Documentation Version**: 2.0
