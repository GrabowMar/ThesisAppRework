# Deploy ThesisApp to Server with All Generated Samples
# This script deploys the app and transfers all generated samples for analysis

param(
    [string]$Server = "ns3086089.ip-145-239-65.eu",
    [string]$User = "ubuntu",
    [string]$SshKey = "$env:USERPROFILE\.ssh\id_ed25519_server"
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ThesisApp Deployment with Samples" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Clone/Update Repository on Server
Write-Host "[1/7] Deploying application code to server..." -ForegroundColor Yellow

# Transfer and run setup script
scp -i $SshKey .\deploy\setup_server.sh ${User}@${Server}:/tmp/setup_server.sh
ssh -i $SshKey $User@$Server "chmod +x /tmp/setup_server.sh && bash /tmp/setup_server.sh"

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to deploy code" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Code deployed" -ForegroundColor Green

# Step 2: Transfer .env file
Write-Host "[2/7] Transferring .env file..." -ForegroundColor Yellow
scp -i $SshKey .\.env ${User}@${Server}:/opt/thesisapp/.env
Write-Host "✓ .env file transferred" -ForegroundColor Green

# Step 3: Transfer generated apps
Write-Host "[3/7] Transferring generated apps (10 models, 100 apps)..." -ForegroundColor Yellow
Write-Host "This may take several minutes..." -ForegroundColor Gray

# First ensure the directory exists
ssh -i $SshKey $User@$Server "mkdir -p /opt/thesisapp/generated/apps"

# Transfer all model folders
$models = Get-ChildItem -Path ".\generated\apps" -Directory
foreach ($model in $models) {
    Write-Host "  Transferring $($model.Name)..." -ForegroundColor Gray
    scp -r -i $SshKey ".\generated\apps\$($model.Name)" "${User}@${Server}:/opt/thesisapp/generated/apps/"
}
Write-Host "✓ All generated apps transferred" -ForegroundColor Green

# Step 4: Transfer metadata
Write-Host "[4/7] Transferring metadata..." -ForegroundColor Yellow
ssh -i $SshKey $User@$Server "mkdir -p /opt/thesisapp/generated/metadata"
scp -r -i $SshKey ".\generated\metadata\*" "${User}@${Server}:/opt/thesisapp/generated/metadata/" 2>$null
Write-Host "✓ Metadata transferred" -ForegroundColor Green

# Step 5: Transfer instance data (database if exists)
Write-Host "[5/7] Transferring database if exists..." -ForegroundColor Yellow
if (Test-Path ".\instance\thesis_app.db") {
    ssh -i $SshKey $User@$Server "mkdir -p /opt/thesisapp/instance"
    scp -i $SshKey ".\instance\thesis_app.db" "${User}@${Server}:/opt/thesisapp/instance/"
    Write-Host "✓ Database transferred" -ForegroundColor Green
} else {
    Write-Host "⊘ No database found, will create fresh" -ForegroundColor Gray
}

# Step 6: Deploy and start services
Write-Host "[6/7] Installing dependencies and starting services..." -ForegroundColor Yellow

# Transfer and run start script
scp -i $SshKey .\deploy\start_services.sh ${User}@${Server}:/tmp/start_services.sh
ssh -i $SshKey $User@$Server "chmod +x /tmp/start_services.sh && bash /tmp/start_services.sh"

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to start services" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Services started" -ForegroundColor Green

# Step 7: Verify deployment
Write-Host "[7/7] Verifying deployment..." -ForegroundColor Yellow
$status = ssh -i $SshKey $User@$Server "cd /opt/thesisapp && docker compose ps --format json" | ConvertFrom-Json

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Deployment Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Count transferred apps
$totalApps = (Get-ChildItem -Path ".\generated\apps" -Directory).Count * 10
Write-Host "✓ Transferred: $totalApps apps from 10 models" -ForegroundColor Green
Write-Host "✓ Server: $Server" -ForegroundColor Green
Write-Host "✓ Application directory: /opt/thesisapp" -ForegroundColor Green

Write-Host ""
Write-Host "Docker Services:" -ForegroundColor Yellow
$status | ForEach-Object {
    $state = if ($_.State -eq "running") { "✓" } else { "✗" }
    $color = if ($_.State -eq "running") { "Green" } else { "Red" }
    Write-Host "  $state $($_.Service): $($_.State)" -ForegroundColor $color
}

Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "1. SSH into server: ssh -i $SshKey $User@$Server" -ForegroundColor White
Write-Host "2. Check logs: cd /opt/thesisapp && docker compose logs -f" -ForegroundColor White
Write-Host "3. Access app at: http://$Server or http://145.239.65.130" -ForegroundColor White
Write-Host "4. Start analysis pipeline (see below)" -ForegroundColor White
Write-Host ""
Write-Host "To start analysis for all 10 apps (per model), run on server:" -ForegroundColor Yellow
Write-Host 'cd /opt/thesisapp' -ForegroundColor Gray
Write-Host 'docker compose exec flask python scripts/analyze_all_samples.py' -ForegroundColor Gray

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
