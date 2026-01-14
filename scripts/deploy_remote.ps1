#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Deploy ThesisApp to remote server with optional clean wipe.

.DESCRIPTION
    This script connects to the remote server via SSH and performs deployment operations.
    It can wipe all data for a clean slate or just restart services.

.PARAMETER Action
    The action to perform: Deploy, Wipe, Restart, Status, Logs

.PARAMETER Server
    The server address (default: ns3086089.ip-145-239-65.eu)

.PARAMETER User
    SSH user (default: root)

.PARAMETER AppPath
    Application path on server (default: /opt/thesisapp)

.EXAMPLE
    .\deploy_remote.ps1 -Action Wipe
    Wipes all data and redeploys with fresh code

.EXAMPLE
    .\deploy_remote.ps1 -Action Deploy
    Pulls latest code and redeploys

.EXAMPLE
    .\deploy_remote.ps1 -Action Status
    Shows container status

.EXAMPLE
    .\deploy_remote.ps1 -Action Logs
    Shows recent logs
#>

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Deploy", "Wipe", "Restart", "Status", "Logs", "Health")]
    [string]$Action,

    [Parameter(Mandatory = $false)]
    [string]$Server = "145.239.65.130",

    [Parameter(Mandatory = $false)]
    [string]$User = "ubuntu",

    [Parameter(Mandatory = $false)]
    [string]$AppPath = "/opt/thesisapp",

    [Parameter(Mandatory = $false)]
    [string]$SshKey = "$env:USERPROFILE\.ssh\id_ed25519_server"
)

$ErrorActionPreference = "Stop"

# Colors for output
function Write-Info { param($Message) Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Success { param($Message) Write-Host "[OK] $Message" -ForegroundColor Green }
function Write-Warn { param($Message) Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Write-Err { param($Message) Write-Host "[ERROR] $Message" -ForegroundColor Red }

function Invoke-RemoteCommand {
    param(
        [string]$Command,
        [string]$Description = ""
    )
    
    if ($Description) {
        Write-Info $Description
    }
    
    $result = ssh -i $SshKey "${User}@${Server}" $Command 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Command failed: $Command"
        Write-Host $result
        return $false
    }
    
    if ($result) {
        Write-Host $result
    }
    return $true
}

function Test-SSHConnection {
    Write-Info "Testing SSH connection to $Server..."
    $result = ssh -i $SshKey -o ConnectTimeout=10 "${User}@${Server}" "echo 'Connected'" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "SSH connection successful"
        return $true
    } else {
        Write-Err "Cannot connect to server. Make sure SSH key is configured."
        Write-Host "SSH Key: $SshKey"
        return $false
    }
}

function Get-Status {
    Write-Info "Getting container status..."
    Invoke-RemoteCommand "cd $AppPath && sudo -u thesisapp docker compose ps" "Container Status:"
    Write-Host ""
    Invoke-RemoteCommand "cd $AppPath && sudo -u thesisapp docker compose ps --format 'table {{.Name}}\t{{.Status}}\t{{.Ports}}'" "Detailed Status:"
}

function Get-Logs {
    Write-Info "Fetching recent logs..."
    Invoke-RemoteCommand "cd $AppPath && sudo -u thesisapp docker compose logs --tail=100" "Recent Logs:"
}

function Get-Health {
    Write-Info "Checking application health..."
    Invoke-RemoteCommand "curl -s http://localhost:5000/health || echo 'Health check failed'" "Health Check:"
    Write-Host ""
    Invoke-RemoteCommand "cd $AppPath && sudo -u thesisapp docker compose ps --format 'table {{.Name}}\t{{.Status}}'" "Service Status:"
}

function Invoke-Restart {
    Write-Info "Restarting services..."
    
    if (-not (Invoke-RemoteCommand "cd $AppPath && sudo -u thesisapp docker compose restart" "Restarting containers...")) {
        return $false
    }
    
    Write-Success "Services restarted"
    Start-Sleep -Seconds 5
    Get-Health
}

function Invoke-Deploy {
    Write-Info "Deploying latest code..."
    
    # Stop containers
    Invoke-RemoteCommand "cd $AppPath && sudo docker compose down" "Stopping containers..."
    
    # Fix git safe directory
    Invoke-RemoteCommand "sudo git config --global --add safe.directory $AppPath" "Configuring git..."
    
    # Pull latest code
    if (-not (Invoke-RemoteCommand "cd $AppPath && sudo git fetch origin main && sudo git reset --hard origin/main" "Pulling latest code...")) {
        Write-Err "Failed to pull code"
        return $false
    }
    
    # Rebuild and start
    if (-not (Invoke-RemoteCommand "cd $AppPath && sudo -u thesisapp docker compose build --parallel" "Building containers...")) {
        Write-Err "Failed to build containers"
        return $false
    }
    
    if (-not (Invoke-RemoteCommand "cd $AppPath && sudo -u thesisapp docker compose up -d" "Starting containers...")) {
        Write-Err "Failed to start containers"
        return $false
    }
    
    Write-Success "Deployment complete"
    Start-Sleep -Seconds 10
    Get-Health
}

function Invoke-Wipe {
    Write-Warn "This will COMPLETELY WIPE all data on the server!"
    Write-Host ""
    Write-Host "  - All generated applications"
    Write-Host "  - All analysis results"  
    Write-Host "  - All database records"
    Write-Host "  - All logs"
    Write-Host ""
    
    $confirmation = Read-Host "Type 'WIPE' to confirm"
    if ($confirmation -ne "WIPE") {
        Write-Info "Operation cancelled"
        return
    }
    
    Write-Info "Starting clean wipe and redeploy..."
    
    # Stop containers
    Write-Info "Stopping containers..."
    Invoke-RemoteCommand "cd $AppPath && sudo docker compose down -v" "Stopping and removing volumes..."
    
    # Fix git safe directory
    Invoke-RemoteCommand "sudo git config --global --add safe.directory $AppPath" "Configuring git..."
    
    # Pull latest code
    Write-Info "Pulling latest code..."
    if (-not (Invoke-RemoteCommand "cd $AppPath && sudo git fetch origin main && sudo git reset --hard origin/main" "Resetting to latest main...")) {
        Write-Err "Failed to pull latest code"
        return $false
    }
    
    # Wipe all data directories
    Write-Info "Wiping data directories..."
    $wipeCommands = @"
cd $AppPath && \
sudo rm -rf generated/apps/* && \
sudo rm -rf generated/raw/payloads/* && \
sudo rm -rf generated/raw/responses/* && \
sudo rm -rf generated/metadata/indices/runs/* && \
sudo rm -rf results/* && \
sudo rm -rf logs/*.log && \
sudo rm -f src/data/thesis_app.db && \
sudo rm -f instance/*.db && \
echo 'Data directories wiped'
"@
    
    if (-not (Invoke-RemoteCommand $wipeCommands "Removing data files...")) {
        Write-Warn "Some files may not have been deleted"
    }
    
    # Prune Docker
    Write-Info "Pruning Docker resources..."
    Invoke-RemoteCommand "sudo docker system prune -f" "Cleaning Docker..."
    
    # Rebuild containers
    Write-Info "Rebuilding containers..."
    if (-not (Invoke-RemoteCommand "cd $AppPath && sudo -u thesisapp docker compose build --no-cache --parallel" "Building fresh containers...")) {
        Write-Err "Failed to build containers"
        return $false
    }
    
    # Start containers
    Write-Info "Starting containers..."
    if (-not (Invoke-RemoteCommand "cd $AppPath && sudo -u thesisapp docker compose up -d" "Starting services...")) {
        Write-Err "Failed to start containers"
        return $false
    }
    
    # Wait for startup
    Write-Info "Waiting for services to start..."
    Start-Sleep -Seconds 15
    
    # Verify
    Write-Success "Clean wipe and redeploy complete!"
    Write-Host ""
    Get-Health
    
    Write-Host ""
    Write-Success "Server is ready at: https://$Server"
}

# Main execution
Write-Host ""
Write-Host "========================================" -ForegroundColor Magenta
Write-Host "  ThesisApp Remote Deployment Tool" -ForegroundColor Magenta  
Write-Host "========================================" -ForegroundColor Magenta
Write-Host ""
Write-Host "Server: $Server"
Write-Host "Action: $Action"
Write-Host ""

# Test SSH connection first
if (-not (Test-SSHConnection)) {
    exit 1
}

# Execute action
switch ($Action) {
    "Status" { Get-Status }
    "Logs" { Get-Logs }
    "Health" { Get-Health }
    "Restart" { Invoke-Restart }
    "Deploy" { Invoke-Deploy }
    "Wipe" { Invoke-Wipe }
}

Write-Host ""
Write-Host "Done!" -ForegroundColor Green
