# Analysis Container Startup Script for Windows
# Starts the analysis container with all tools

Write-Host "Starting Analysis Container for Thesis Research Platform..." -ForegroundColor Green

# Check if Docker is running
try {
    docker info | Out-Null
} catch {
    Write-Host "Error: Docker is not running. Please start Docker first." -ForegroundColor Red
    exit 1
}

# Create necessary directories
Write-Host "Creating directories..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "analysis-results" | Out-Null
New-Item -ItemType Directory -Force -Path "temp" | Out-Null
New-Item -ItemType Directory -Force -Path "logs" | Out-Null

# Build and start the analysis container
Write-Host "Building analysis container..." -ForegroundColor Yellow
docker-compose -f docker-compose.analysis.yml build

Write-Host "Starting analysis container..." -ForegroundColor Yellow
docker-compose -f docker-compose.analysis.yml up -d

# Wait for container to be ready
Write-Host "Waiting for container to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Check container health
Write-Host "Checking container health..." -ForegroundColor Yellow
$ready = $false
for ($i = 1; $i -le 30; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8080/health" -Method GET -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            Write-Host "✓ Analysis container is healthy and ready!" -ForegroundColor Green
            $ready = $true
            break
        }
    } catch {
        Write-Host "Waiting for container... ($i/30)" -ForegroundColor Yellow
        Start-Sleep -Seconds 2
    }
}

if (-not $ready) {
    Write-Host "Warning: Container health check timed out" -ForegroundColor Yellow
}

# Show container status
Write-Host ""
Write-Host "Container Status:" -ForegroundColor Cyan
docker-compose -f docker-compose.analysis.yml ps

Write-Host ""
Write-Host "Available Analysis Tools:" -ForegroundColor Cyan
try {
    $toolsResponse = Invoke-WebRequest -Uri "http://localhost:8080/tools" -Method GET
    $toolsResponse.Content | ConvertFrom-Json | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Container not responding to tools request" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Analysis container is ready!" -ForegroundColor Green
Write-Host "API available at: http://localhost:8080" -ForegroundColor Cyan
Write-Host "Health check: Invoke-WebRequest http://localhost:8080/health" -ForegroundColor Gray
Write-Host "Tools list: Invoke-WebRequest http://localhost:8080/tools" -ForegroundColor Gray
Write-Host ""
Write-Host "To stop the container: docker-compose -f docker-compose.analysis.yml down" -ForegroundColor Gray
