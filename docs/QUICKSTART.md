# Quick Start Guide

## Prerequisites

- **Windows** (Recommended) or Linux/Mac
- **Python 3.10+**
- **Docker Desktop** (for analyzer services)
- **PowerShell 7+** (for orchestration scripts)

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/GrabowMar/ThesisAppRework.git
   cd ThesisAppRework
   ```

2. **Run the orchestrator**:
   The `start.ps1` script handles setup, dependencies, and startup.
   ```powershell
   ./start.ps1
   ```

## Running the Application

### Interactive Mode (Recommended)
Run `./start.ps1` and choose an option from the menu:
- **[S] Start**: Launches the full stack (Flask app + Analyzer services).
- **[D] Dev**: Runs Flask in developer mode (faster startup, no analyzers).
- **[L] Logs**: View aggregated logs from all services.
- **[M] Monitor**: Real-time status dashboard.

### Command Line Options
- Start full stack: `./start.ps1 -Mode Start`
- Start dev mode: `./start.ps1 -Mode Dev -NoAnalyzer`
- Stop all services: `./start.ps1 -Mode Stop`

## Accessing the App

- **Web Interface**: http://localhost:5000
- **API**: http://localhost:5000/api
- **Analyzer Services**:
  - Static Analysis: ws://localhost:2001
  - Dynamic Analysis: ws://localhost:2002
  - Performance: ws://localhost:2003
  - AI Analysis: ws://localhost:2004

## First Steps

1. **Login**: Use the default admin credentials (printed in logs on first run) or reset via `./start.ps1 -Mode Password`.
2. **Generate an App**: Go to **Generation** and select a model.
3. **Run Analysis**: Navigate to **Analysis**, select the generated app, and choose an analysis profile (e.g., "Security Scan").
4. **View Results**: Check the **Dashboard** for real-time progress and detailed reports.
