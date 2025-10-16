#!/usr/bin/env pwsh
# Rebuild Analyzer Containers with New Tools
# ===========================================
# This script rebuilds all analyzer containers with the newly added tools.

param(
    [switch]$Force,
    [switch]$NoBuild,
    [string]$Service = ""
)

Write-Host "🔧 ThesisApp Analyzer Container Rebuild Script" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

# Check if Docker is running
try {
    docker info | Out-Null
    Write-Host "✅ Docker is running" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker is not running. Please start Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Navigate to analyzer directory
Set-Location $PSScriptRoot\analyzer

# Check if analyzer containers exist
Write-Host "`n🔍 Checking for existing analyzer containers..." -ForegroundColor Yellow
$existingImages = docker images --format "{{.Repository}}:{{.Tag}}" | Select-String "analyzer"
if (-not $existingImages) {
    Write-Host "⚠️  No analyzer containers found. Will build from scratch." -ForegroundColor Yellow
    $Force = $true
} else {
    Write-Host "✅ Found existing analyzer containers" -ForegroundColor Green
}

Write-Host "`n📦 New Tools Added:" -ForegroundColor Yellow
Write-Host "  Static Analyzer:" -ForegroundColor White
Write-Host "    • Semgrep (multi-language SAST)" -ForegroundColor Gray
Write-Host "    • Snyk Code (AI-powered vulnerability scanner)" -ForegroundColor Gray
Write-Host "    • Mypy (Python type checker)" -ForegroundColor Gray
Write-Host "    • Safety (Python dependency scanner)" -ForegroundColor Gray
Write-Host "    • JSHint (JavaScript quality checker)" -ForegroundColor Gray
Write-Host "    • Vulture (Python dead code detector)" -ForegroundColor Gray
Write-Host "  Performance Tester:" -ForegroundColor White
Write-Host "    • Artillery (modern load testing)" -ForegroundColor Gray
Write-Host "  AI Analyzer:" -ForegroundColor White
Write-Host "    • GPT4All (local AI models)" -ForegroundColor Gray

Write-Host "`n🛑 Stopping existing containers..." -ForegroundColor Yellow
docker-compose down

if ($Force) {
    Write-Host "`n🗑️ Removing existing images..." -ForegroundColor Yellow
    docker-compose down --rmi all --volumes
}

Write-Host "`n🔨 Building new containers..." -ForegroundColor Yellow
if ($Service) {
    Write-Host "Building specific service: $Service" -ForegroundColor Gray
    docker-compose build --no-cache $Service
} else {
    docker-compose build --no-cache
}

if (-not $NoBuild) {
    Write-Host "`n🚀 Starting analyzer services..." -ForegroundColor Yellow
    docker-compose up -d
    
    Write-Host "`n⏳ Waiting for services to become healthy..." -ForegroundColor Yellow
    Start-Sleep 10
    
    Write-Host "`n📊 Checking service status..." -ForegroundColor Yellow
    docker-compose ps
    
    Write-Host "`n🔍 Health check status:" -ForegroundColor Yellow
    $services = @("static-analyzer", "performance-tester", "ai-analyzer", "gateway", "redis")
    foreach ($service in $services) {
        $status = docker-compose exec -T $service python -c "print('healthy')" 2>$null
        if ($status -match "healthy") {
            Write-Host "  ✅ $service" -ForegroundColor Green
        } else {
            Write-Host "  ❌ $service" -ForegroundColor Red
        }
    }
    
    Write-Host "`n📋 Service URLs:" -ForegroundColor Cyan
    Write-Host "  Gateway:           ws://localhost:8765" -ForegroundColor White
    Write-Host "  Static Analyzer:   ws://localhost:2001" -ForegroundColor White
    Write-Host "  Dynamic Analyzer:  ws://localhost:2002" -ForegroundColor White
    Write-Host "  Performance:       ws://localhost:2003" -ForegroundColor White
    Write-Host "  AI Analyzer:       ws://localhost:2004" -ForegroundColor White
    Write-Host "  Redis:             redis://localhost:6379" -ForegroundColor White
}

Write-Host "`n✅ Container rebuild complete!" -ForegroundColor Green
Write-Host "💡 Use these commands to manage the analyzers:" -ForegroundColor Yellow
Write-Host "  docker-compose logs <service>  # View logs" -ForegroundColor Gray
Write-Host "  docker-compose ps             # Check status" -ForegroundColor Gray
Write-Host "  docker-compose restart        # Restart all" -ForegroundColor Gray
Write-Host "  docker-compose down           # Stop all" -ForegroundColor Gray

if ($Service) {
    Write-Host "`n🎯 To test the specific service you built:" -ForegroundColor Cyan
    Write-Host "  docker-compose exec $Service python main.py --test" -ForegroundColor White
}

Write-Host "`n🧪 To test new tools:" -ForegroundColor Cyan
Write-Host "  Static Analyzer: Test with Semgrep, Snyk, Mypy, Safety, JSHint, Vulture" -ForegroundColor White
Write-Host "  Performance:     Test with Artillery load testing" -ForegroundColor White
Write-Host "  AI Analyzer:     Test with GPT4All local models" -ForegroundColor White