# Quick Start Guide

Get up and running with ThesisAppRework in under 5 minutes.

## Prerequisites

Before starting, ensure you have:

- **Python 3.10+** - [Download](https://www.python.org/downloads/)
- **Docker Desktop** - [Download](https://www.docker.com/products/docker-desktop/)
- **Git** - [Download](https://git-scm.com/downloads)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/GrabowMar/ThesisAppRework.git
cd ThesisAppRework
```

### 2. Create Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Linux/macOS:**
```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and set your API key:
```
OPENROUTER_API_KEY=sk-or-v1-your-key-here
SECRET_KEY=your-secret-key-here
```

### 5. Initialize Database

```bash
python src/init_db.py
```

## Running the Application

### Interactive Mode (Recommended)

```bash
./start.ps1
```

This opens an interactive menu with options:

| Mode | Description |
|------|-------------|
| `Start` | Full stack (Flask + Analyzers) |
| `Stop` | Stop all services |
| `Dev` | Development mode (Flask only, debug on) |
| `Status` | Status dashboard |
| `Logs` | Tail all logs |
| `Rebuild` | Fast incremental container rebuild |
| `CleanRebuild` | Full rebuild without cache |
| `Maintenance` | Manual cleanup (7-day orphan grace) |
| `Reload` | Hot reload for code changes |
| `Wipeout` | Full reset (WARNING: data loss) |
| `Password` | Reset admin password |
| `Health` | Check service health |

> **Note**: Maintenance is now manual by default (as of Nov 2025). Orphan apps get a 7-day grace period before deletion.

### Quick Commands

| Command | Description |
|---------|-------------|
| `./start.ps1 -Mode Start` | Start Flask + all analyzers |
| `./start.ps1 -Mode Dev` | Start Flask only (fast) |
| `./start.ps1 -Mode Stop` | Stop all services |
| `./start.ps1 -Mode Status` | View dashboard |
| `./start.ps1 -Mode Maintenance` | Run cleanup manually |
| `./start.ps1 -Mode Health` | Check service health |

### Direct Python

```bash
python src/main.py
```

Access the application at **http://localhost:5000**

## First Analysis

### Using the Web UI

1. Navigate to http://localhost:5000
2. Log in or create an account
3. Go to **Analysis → Create New**
4. Select a model and app number
5. Choose analysis type (e.g., "comprehensive")
6. Click **Start Analysis**

### Using the CLI

```bash
# Start analyzer containers
python analyzer/analyzer_manager.py start

# Run analysis
python analyzer/analyzer_manager.py analyze openai_gpt-4 1 comprehensive

# View results
python analyzer/analyzer_manager.py status
```

## Verifying Installation

### Check Flask

```bash
curl http://localhost:5000/api/health
```

Expected: `{"status": "healthy"}`

### Check Analyzers

```bash
python analyzer/analyzer_manager.py health
```

All services should show "healthy" status.

## Common Issues

### Port 5000 Already in Use

```bash
# Stop all services
./start.ps1 -Mode Stop

# Or manually kill process
netstat -ano | findstr :5000
taskkill /PID <PID> /F
```

### Docker Not Running

Ensure Docker Desktop is running before starting analyzers.

### Missing API Key

If AI analysis fails, verify `OPENROUTER_API_KEY` is set in `.env`.

## Next Steps

- [Architecture Overview](ARCHITECTURE.md) - Understand the system design
- [Background Services](BACKGROUND_SERVICES.md) - Task execution and maintenance
- [API Reference](api-reference.md) - REST API documentation
- [Development Guide](development-guide.md) - Contributing and testing
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues and solutions
