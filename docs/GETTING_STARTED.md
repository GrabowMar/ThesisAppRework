# Getting Started with ThesisApp

> Complete setup and first-run guide for the AI Model Analysis Platform

---

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Starting Services](#starting-services)
- [Your First Analysis](#your-first-analysis)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

| Software | Version | Purpose |
|----------|---------|---------|
| **Python** | 3.9+ | Application runtime |
| **Docker** | Latest | Container orchestration |
| **Docker Compose** | Latest | Multi-container management |
| **Redis** | Latest | Task queue and caching |

### Optional Software

| Software | Version | Purpose |
|----------|---------|---------|
| **PostgreSQL** | 12+ | Production database (SQLite for dev) |
| **Git** | Latest | Version control |

### System Requirements

```
Minimum:
- 8GB RAM
- 4 CPU cores
- 20GB disk space

Recommended:
- 16GB RAM
- 8 CPU cores
- 50GB disk space
```

---

## Installation

### Step 1: Clone Repository

```bash
git clone https://github.com/YourOrg/ThesisAppRework.git
cd ThesisAppRework
```

### Step 2: Python Environment

<details>
<summary><b>Windows (PowerShell)</b></summary>

```powershell
# Create virtual environment
python -m venv .venv

# Activate
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

</details>

<details>
<summary><b>Linux/macOS</b></summary>

```bash
# Create virtual environment
python3 -m venv .venv

# Activate
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

</details>

### Step 3: Verify Installation

```bash
# Check Python packages
pip list | grep -E "flask|celery|redis|sqlalchemy"

# Check Docker
docker --version
docker-compose --version

# Check Redis
redis-cli ping  # Should return "PONG"
```

---

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Copy example file
cp .env.example .env
```

Edit `.env` with your settings:

```bash
# ============================================
# Core Settings
# ============================================
FLASK_SECRET_KEY=change-this-to-random-string
FLASK_ENV=development
DEBUG=True

# ============================================
# AI Model Access
# ============================================
OPENROUTER_API_KEY=sk-or-v1-your-key-here
# Get your key from: https://openrouter.ai/keys

# ============================================
# Database
# ============================================
# Development (SQLite)
DATABASE_URL=sqlite:///app.db

# Production (PostgreSQL)
# DATABASE_URL=postgresql://user:pass@localhost:5432/thesisapp

# ============================================
# Redis (Task Queue)
# ============================================
REDIS_URL=redis://localhost:6379/0

# ============================================
# Analyzer Services
# ============================================
ANALYZER_TIMEOUT=300
WEBSOCKET_GATEWAY_URL=ws://localhost:8765

# ============================================
# Optional: Disable Models
# ============================================
# Skip analysis for specific models (comma-separated)
# DISABLED_ANALYSIS_MODELS=model1,model2
```

### API Key Setup

```mermaid
graph LR
    A[Get API Key] --> B[Visit OpenRouter.ai]
    B --> C[Create Account]
    C --> D[Generate Key]
    D --> E[Add to .env]
    E --> F[Restart Services]
    
    style A fill:#4CAF50
    style E fill:#FF9800
    style F fill:#2196F3
```

---

## Starting Services

### Quick Start (All Services)

```bash
# Use convenience script
./start.ps1  # Windows
./start.sh   # Linux/macOS
```

### Manual Start (Step-by-Step)

#### 1. Initialize Database

```bash
cd src
python init_db.py
```

Expected output:
```
✓ Database created: src/app.db
✓ Tables created: 12 tables
✓ Sample data loaded
```

#### 2. Start Analyzer Services

```bash
cd analyzer
docker-compose up -d
```

Verify services:
```bash
docker-compose ps
```

Expected output:
```
NAME                  STATUS    PORTS
static-analyzer       Up        0.0.0.0:2001->2001/tcp
dynamic-analyzer      Up        0.0.0.0:2002->2002/tcp
performance-tester    Up        0.0.0.0:2003->2003/tcp
ai-analyzer          Up        0.0.0.0:2004->2004/tcp
websocket-gateway     Up        0.0.0.0:8765->8765/tcp
```

#### 3. Start Flask Application

```bash
# Terminal 1
cd src
python main.py
```

Expected output:
```
 * Running on http://127.0.0.1:5000
 * Debug mode: on
```

#### 4. Start Celery Worker

```bash
# Terminal 2
cd src
celery -A app.tasks worker --loglevel=info
```

Expected output:
```
[tasks]
  . app.tasks.analyze_application
  . app.tasks.generate_application

celery@hostname ready.
```

### Service Health Check

```bash
# Check all services
python analyzer/analyzer_manager.py health
```

Expected output:
```
✓ Flask App       : http://localhost:5000         [OK]
✓ Redis           : redis://localhost:6379        [OK]
✓ Static Analyzer : http://localhost:2001         [OK]
✓ Dynamic Analyzer: http://localhost:2002         [OK]
✓ Performance     : http://localhost:2003         [OK]
✓ AI Analyzer     : http://localhost:2004         [OK]
✓ WebSocket       : ws://localhost:8765           [OK]
```

---

## Your First Analysis

### Option 1: Web Interface

```mermaid
graph LR
    A[Open Browser] --> B[localhost:5000]
    B --> C[Navigate to Models]
    C --> D[Select Model]
    D --> E[Generate App]
    E --> F[View Results]
    
    style A fill:#4CAF50
    style E fill:#FF9800
    style F fill:#2196F3
```

1. **Open Browser**: Navigate to http://localhost:5000
2. **Dashboard**: View system status and recent activity
3. **Models Page**: Click "Models" in sidebar
4. **Generate App**:
   - Click "Generate Sample" on any model
   - Select template (e.g., "Login Backend")
   - Click "Generate"
5. **Monitor Progress**: Watch real-time generation status
6. **View Application**: Once complete, click "View Details"
7. **Run Analysis**:
   - Click "Analyze" button
   - Select analysis types (Security, Performance, etc.)
   - Monitor progress
8. **View Results**: Click "View Results" when complete

### Option 2: Command Line

```bash
# Generate and analyze in one command
python analyzer/analyzer_manager.py analyze anthropic_claude-3.5-sonnet 1

# Or step-by-step:
# 1. Generate app
python analyzer/analyzer_manager.py generate anthropic_claude-3.5-sonnet 1

# 2. Run specific analysis
python analyzer/analyzer_manager.py analyze anthropic_claude-3.5-sonnet 1 security

# 3. View results
python analyzer/analyzer_manager.py results
```

### Understanding Results

Results are saved in multiple formats:

```
results/
└── anthropic_claude-3.5-sonnet/
    └── app1/
        ├── analysis/
        │   ├── task_YYYYMMDD_HHMMSS.json    # Consolidated results
        │   ├── security_results.json         # Security-specific
        │   ├── performance_results.json      # Performance-specific
        │   └── quality_results.json          # Code quality
        └── metadata.json                     # App metadata
```

---

## Troubleshooting

### Common Issues

<details>
<summary><b>Port Already in Use</b></summary>

**Error**: `Address already in use: port 5000`

**Solution**:
```bash
# Find process using port
netstat -ano | findstr :5000  # Windows
lsof -i :5000                 # Linux/macOS

# Kill process
taskkill /PID <pid> /F        # Windows
kill -9 <pid>                 # Linux/macOS
```

</details>

<details>
<summary><b>Docker Services Not Starting</b></summary>

**Error**: `Cannot connect to Docker daemon`

**Solution**:
```bash
# Start Docker Desktop (Windows/macOS)
# Or start Docker daemon (Linux)
sudo systemctl start docker

# Rebuild containers
cd analyzer
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

</details>

<details>
<summary><b>Redis Connection Failed</b></summary>

**Error**: `Error 111 connecting to localhost:6379`

**Solution**:
```bash
# Windows: Install Redis via Chocolatey
choco install redis-64
redis-server

# Linux: Install and start
sudo apt-get install redis-server
sudo systemctl start redis

# macOS: Install via Homebrew
brew install redis
brew services start redis
```

</details>

<details>
<summary><b>Database Migration Issues</b></summary>

**Error**: `OperationalError: no such table`

**Solution**:
```bash
# Delete and recreate database
cd src
rm -f app.db  # or del app.db on Windows
python init_db.py
```

</details>

<details>
<summary><b>API Key Invalid</b></summary>

**Error**: `401 Unauthorized` or `Invalid API key`

**Solution**:
1. Verify key in `.env` file
2. Check key format: `sk-or-v1-...` (OpenRouter)
3. Ensure no extra spaces or quotes
4. Test key directly:
```bash
curl https://openrouter.ai/api/v1/models \
  -H "Authorization: Bearer $OPENROUTER_API_KEY"
```

</details>

---

## Next Steps

Now that you're set up, explore these guides:

1. **[Generate Applications](guides/GENERATING_APPS.md)** - Create AI-generated apps
2. **[Run Analysis](guides/RUNNING_ANALYSIS.md)** - Execute comprehensive tests
3. **[Manage Applications](guides/MANAGING_APPS.md)** - Control app lifecycle
4. **[Batch Operations](guides/BATCH_OPERATIONS.md)** - Process at scale

---

## Quick Reference

### Essential Commands

```bash
# Start all services
./start.ps1  # or ./start.sh

# Stop all services
docker-compose -f analyzer/docker-compose.yml down
# Ctrl+C in Flask and Celery terminals

# Health check
python analyzer/analyzer_manager.py health

# View logs
python analyzer/analyzer_manager.py logs [service] [lines]

# List generated apps
python analyzer/analyzer_manager.py list

# Clean results
rm -rf results/*  # Use with caution!
```

### Key URLs

| Service | URL |
|---------|-----|
| **Web UI** | http://localhost:5000 |
| **API Docs** | http://localhost:5000/api/docs |
| **Static Analyzer** | http://localhost:2001 |
| **Dynamic Analyzer** | http://localhost:2002 |
| **Performance Tester** | http://localhost:2003 |
| **AI Analyzer** | http://localhost:2004 |
| **WebSocket Gateway** | ws://localhost:8765 |

---

**Need Help?** Check our [Troubleshooting Guide](guides/TROUBLESHOOTING.md) or [open an issue](https://github.com/YourOrg/ThesisAppRework/issues).
