# AI Client Scripts

Three convenient client scripts for AI models (Claude, GPT-4, etc.) to interact with the Thesis Platform API.

## 🚀 Quick Start

### 1. Get Your Token

**Using Python:**
```bash
python scripts/ai_client.py get-token --username admin --password admin123
```

**Using PowerShell:**
```powershell
.\scripts\ai_client.ps1 -Command get-token -Username admin -Password admin123
```

**Using Bash:**
```bash
bash scripts/ai_client.sh get-token --username admin --password admin123
```

### 2. Set Environment Variable

**PowerShell:**
```powershell
$env:THESIS_PLATFORM_TOKEN = "your-token-here"
```

**Bash:**
```bash
export THESIS_PLATFORM_TOKEN="your-token-here"
```

### 3. Use the API

```bash
# List models
python scripts/ai_client.py list-models

# Get statistics
python scripts/ai_client.py stats

# Generate app
python scripts/ai_client.py generate --model openai_gpt-4 --template 1 --name my-app
```

## 📜 Scripts Overview

### `ai_client.py` (Python)
- **Best for**: Cross-platform, programmatic usage
- **Requirements**: Python 3.6+ (no external dependencies)
- **Features**: Full API coverage, interactive mode

### `ai_client.ps1` (PowerShell)
- **Best for**: Windows users, PowerShell scripts
- **Requirements**: PowerShell 5.1+ or PowerShell Core
- **Features**: Native Windows experience

### `ai_client.sh` (Bash)
- **Best for**: Linux/macOS, CI/CD pipelines
- **Requirements**: bash, curl, python3 (for JSON formatting)
- **Features**: Lightweight, scriptable

## 📚 Available Commands

All three scripts support these commands:

| Command | Description | Example |
|---------|-------------|---------|
| `get-token` | Login and generate token | `--username admin --password admin123` |
| `list-models` | List all AI models | No arguments |
| `list-apps` | List generated applications | No arguments |
| `stats` | Get dashboard statistics | No arguments |
| `health` | System health check | No arguments (no auth) |
| `verify` | Verify token validity | No arguments |
| `generate` | Generate new application | `--model M --template T --name N` |
| `interactive` | Interactive mode | No arguments |

## 🎯 Usage Examples

### Python Examples

```bash
# Get help
python scripts/ai_client.py --help

# List all models
python scripts/ai_client.py --token YOUR_TOKEN list-models

# Get statistics with custom base URL
python scripts/ai_client.py --base-url http://example.com --token TOKEN stats

# Generate application
python scripts/ai_client.py --token TOKEN generate \
  --model openai_gpt-4 \
  --template 1 \
  --name my-awesome-app \
  --description "A sample React app"

# Interactive mode
python scripts/ai_client.py --token TOKEN
```

### PowerShell Examples

```powershell
# Get help
.\scripts\ai_client.ps1 -Help

# List models
.\scripts\ai_client.ps1 -Token YOUR_TOKEN -Command list-models

# Generate app
.\scripts\ai_client.ps1 -Token TOKEN -Command generate `
  -Model openai_gpt-4 `
  -Template 1 `
  -Name my-app

# Interactive mode
.\scripts\ai_client.ps1 -Token TOKEN -Command interactive
```

### Bash Examples

```bash
# Get help
bash scripts/ai_client.sh --help

# List models
bash scripts/ai_client.sh --token YOUR_TOKEN list-models

# Generate app
bash scripts/ai_client.sh --token TOKEN generate \
  --model openai_gpt-4 \
  --template 1 \
  --name my-app

# Interactive mode
bash scripts/ai_client.sh --token TOKEN interactive
```

## 🤖 For AI Models (Claude, GPT-4, etc.)

### Step 1: User Provides Credentials

User gives you:
```
Base URL: http://localhost:5000
Token: abc123xyz789...
```

### Step 2: Choose Your Script

**Python (recommended):**
```python
# User runs this to get the token
python scripts/ai_client.py get-token --username admin --password admin123

# Then exports it
export THESIS_PLATFORM_TOKEN="the-token"

# You can now use any command
python scripts/ai_client.py list-models
python scripts/ai_client.py stats
```

**PowerShell:**
```powershell
$env:THESIS_PLATFORM_TOKEN = "the-token"
.\scripts\ai_client.ps1 -Command list-models
```

**Bash:**
```bash
export THESIS_PLATFORM_TOKEN="the-token"
bash scripts/ai_client.sh list-models
```

### Step 3: Interact with Platform

The AI can now execute commands like:
- List available models
- Generate applications
- Get system statistics
- Verify token validity

## 🔧 Advanced Usage

### Custom Base URL

```bash
# Python
python scripts/ai_client.py --base-url https://platform.example.com --token TOKEN list-models

# PowerShell
.\scripts\ai_client.ps1 -BaseUrl https://platform.example.com -Token TOKEN -Command list-models

# Bash
bash scripts/ai_client.sh --base-url https://platform.example.com --token TOKEN list-models
```

### Environment Variables

Set these for convenience:

```bash
# Bash/Linux/macOS
export THESIS_PLATFORM_URL="http://localhost:5000"
export THESIS_PLATFORM_TOKEN="your-token"

# PowerShell
$env:THESIS_PLATFORM_URL = "http://localhost:5000"
$env:THESIS_PLATFORM_TOKEN = "your-token"
```

Then run commands without flags:
```bash
python scripts/ai_client.py list-models
.\scripts\ai_client.ps1 -Command stats
bash scripts/ai_client.sh health
```

## 📦 Generate Application Example

Full example with all options:

```bash
python scripts/ai_client.py --token YOUR_TOKEN generate \
  --model "openai_gpt-4" \
  --template 1 \
  --name "my-react-app" \
  --description "A sample React application with authentication"
```

Response:
```json
{
  "success": true,
  "task_id": "abc-123",
  "status": "pending",
  "message": "Generation started"
}
```

## 🔍 Interactive Mode

All scripts support interactive mode for exploring the API:

```bash
# Python
python scripts/ai_client.py --token TOKEN

# PowerShell
.\scripts\ai_client.ps1 -Token TOKEN -Command interactive

# Bash
bash scripts/ai_client.sh --token TOKEN interactive
```

Interactive menu:
```
╔════════════════════════════════════════════════════════════╗
║   Thesis Platform - Interactive AI Client                 ║
╚════════════════════════════════════════════════════════════╝

Available Commands:
  1. List Models
  2. List Applications
  3. Get Statistics
  4. Health Check
  5. Verify Token
  q. Quit

Enter command: _
```

## 🛠️ Troubleshooting

### "Authentication required but no token provided"
→ Set the token: `export THESIS_PLATFORM_TOKEN="your-token"`

### "Connection error"
→ Check the base URL and ensure the platform is running

### "Invalid or expired token"
→ Generate a new token with the `get-token` command

### Python script not found
→ Run from project root: `python scripts/ai_client.py ...`

### Permission denied (bash)
→ Make executable: `chmod +x scripts/ai_client.sh`

## 📖 See Also

- [API Token Authentication Guide](../docs/API_TOKEN_AUTHENTICATION.md)
- [AI Quick Start Guide](../docs/AI_API_QUICK_START.md)
- [API Documentation](../docs/RESEARCH_API_DOCUMENTATION.md)

## 💡 Tips

1. **Save your token** - It's only shown once when generated
2. **Use environment variables** - Cleaner than passing --token every time
3. **Try interactive mode** - Great for exploring the API
4. **Health check first** - Verify connectivity before authenticating
5. **Check token validity** - Use `verify` command to test your token
