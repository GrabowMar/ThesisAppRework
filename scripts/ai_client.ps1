# AI Client for Thesis Platform - PowerShell Version
# Pure PowerShell implementation for Windows users

param(
    [string]$BaseUrl = $env:THESIS_PLATFORM_URL ?? "http://localhost:5000",
    [string]$Token = $env:THESIS_PLATFORM_TOKEN ?? "",
    [string]$Command = "",
    [string]$Username = "",
    [string]$Password = "",
    [string]$Model = "",
    [int]$Template = 0,
    [string]$Name = "",
    [string]$Description = "",
    [switch]$Help
)

# Colors
function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Type = "Info"
    )
    
    switch ($Type) {
        "Success" { Write-Host "✅ $Message" -ForegroundColor Green }
        "Error" { Write-Host "❌ Error: $Message" -ForegroundColor Red }
        "Warning" { Write-Host "⚠️  $Message" -ForegroundColor Yellow }
        "Info" { Write-Host "ℹ️  $Message" -ForegroundColor Cyan }
        default { Write-Host $Message }
    }
}

# Show usage
function Show-Usage {
    Write-Host @"
AI Client for Thesis Platform - PowerShell Version

Usage: .\ai_client.ps1 [OPTIONS] -Command COMMAND

Options:
    -BaseUrl URL        Base URL of the platform (default: http://localhost:5000)
    -Token TOKEN        API authentication token
    -Help               Show this help message

Commands:
    get-token          Login and generate an API token
    list-models        List all available AI models
    list-apps          List all generated applications
    stats              Get dashboard statistics
    health             Check system health
    verify             Verify token is valid
    generate           Generate a new application
    interactive        Start interactive mode

Environment Variables:
    THESIS_PLATFORM_URL     Base URL (alternative to -BaseUrl)
    THESIS_PLATFORM_TOKEN   API token (alternative to -Token)

Examples:
    # Get a token
    .\ai_client.ps1 -Command get-token -Username admin -Password admin123

    # Set token in environment
    `$env:THESIS_PLATFORM_TOKEN = "your-token-here"

    # List models
    .\ai_client.ps1 -Command list-models

    # Generate application
    .\ai_client.ps1 -Command generate -Model openai_gpt-4 -Template 1 -Name my-app

    # Interactive mode
    .\ai_client.ps1 -Command interactive
"@
    exit 0
}

# Make API request
function Invoke-ApiRequest {
    param(
        [string]$Endpoint,
        [string]$Method = "GET",
        [object]$Body = $null,
        [bool]$RequireAuth = $true
    )
    
    $url = "$BaseUrl$Endpoint"
    $headers = @{
        "Content-Type" = "application/json"
    }
    
    if ($RequireAuth) {
        if ([string]::IsNullOrEmpty($Token)) {
            Write-ColorOutput "Authentication required but no token provided" "Error"
            Write-ColorOutput "Use: `$env:THESIS_PLATFORM_TOKEN='your-token' or -Token parameter" "Info"
            exit 1
        }
        $headers["Authorization"] = "Bearer $Token"
    }
    
    try {
        $params = @{
            Uri = $url
            Method = $Method
            Headers = $headers
        }
        
        if ($Body) {
            $params["Body"] = ($Body | ConvertTo-Json -Depth 10)
        }
        
        $response = Invoke-RestMethod @params
        return $response
    }
    catch {
        Write-ColorOutput $_.Exception.Message "Error"
        exit 1
    }
}

# Get token
function Get-Token {
    if ([string]::IsNullOrEmpty($Username) -or [string]::IsNullOrEmpty($Password)) {
        Write-ColorOutput "Username and password required" "Error"
        Write-Host "Usage: .\ai_client.ps1 -Command get-token -Username USER -Password PASS"
        exit 1
    }
    
    Write-ColorOutput "Logging in as $Username..." "Info"
    
    try {
        # Login to get session
        $loginUrl = "$BaseUrl/auth/login"
        $loginBody = @{
            username = $Username
            password = $Password
        }
        
        $session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
        $loginParams = @{
            Uri = $loginUrl
            Method = "POST"
            Body = $loginBody
            WebSession = $session
            MaximumRedirection = 0
            ErrorAction = "SilentlyContinue"
        }
        
        Invoke-WebRequest @loginParams | Out-Null
        
        # Generate token
        $tokenUrl = "$BaseUrl/api/tokens/generate"
        $tokenParams = @{
            Uri = $tokenUrl
            Method = "POST"
            WebSession = $session
        }
        
        $response = Invoke-RestMethod @tokenParams
        
        if ($response.success) {
            Write-ColorOutput "Token generated successfully!" "Success"
            Write-Host ""
            Write-Host "🔑 Your API Token:"
            Write-Host $response.token
            Write-Host ""
            Write-Host "💡 Save this token! Use it with:"
            Write-Host "   `$env:THESIS_PLATFORM_TOKEN = '$($response.token)'"
            Write-Host "   .\ai_client.ps1 -Command list-models"
        }
        else {
            Write-ColorOutput "Failed to generate token" "Error"
        }
    }
    catch {
        Write-ColorOutput $_.Exception.Message "Error"
        exit 1
    }
}

# List models
function Get-Models {
    Write-ColorOutput "Fetching available models..." "Info"
    $response = Invoke-ApiRequest -Endpoint "/api/models"
    Write-ColorOutput "Found $($response.models.Count) models" "Success"
    $response | ConvertTo-Json -Depth 10
}

# List applications
function Get-Applications {
    Write-ColorOutput "Fetching generated applications..." "Info"
    $response = Invoke-ApiRequest -Endpoint "/api/applications"
    Write-ColorOutput "Applications retrieved" "Success"
    $response | ConvertTo-Json -Depth 10
}

# Get statistics
function Get-Stats {
    Write-ColorOutput "Fetching dashboard statistics..." "Info"
    $response = Invoke-ApiRequest -Endpoint "/api/dashboard/stats"
    Write-ColorOutput "Statistics retrieved" "Success"
    $response | ConvertTo-Json -Depth 10
}

# Health check
function Get-Health {
    Write-ColorOutput "Checking system health..." "Info"
    $response = Invoke-ApiRequest -Endpoint "/api/health" -RequireAuth $false
    Write-ColorOutput "Health check complete" "Success"
    $response | ConvertTo-Json -Depth 10
}

# Verify token
function Test-Token {
    Write-ColorOutput "Verifying token..." "Info"
    $response = Invoke-ApiRequest -Endpoint "/api/tokens/verify"
    
    if ($response.valid) {
        Write-ColorOutput "Token is valid!" "Success"
    }
    else {
        Write-ColorOutput "Token is invalid!" "Error"
    }
    
    $response | ConvertTo-Json -Depth 10
}

# Generate application
function New-Application {
    if ([string]::IsNullOrEmpty($Model) -or $Template -eq 0 -or [string]::IsNullOrEmpty($Name)) {
        Write-ColorOutput "Model, template, and name are required" "Error"
        Write-Host "Usage: .\ai_client.ps1 -Command generate -Model MODEL -Template ID -Name NAME"
        exit 1
    }
    
    $body = @{
        model = $Model
        template_id = $Template
        app_name = $Name
    }
    
    if (![string]::IsNullOrEmpty($Description)) {
        $body["description"] = $Description
    }
    
    Write-ColorOutput "Generating application '$Name' with $Model..." "Info"
    $response = Invoke-ApiRequest -Endpoint "/api/gen/generate" -Method "POST" -Body $body
    Write-ColorOutput "Generation request submitted!" "Success"
    $response | ConvertTo-Json -Depth 10
}

# Interactive mode
function Start-Interactive {
    Clear-Host
    Write-Host "╔════════════════════════════════════════════════════════════╗"
    Write-Host "║   Thesis Platform - Interactive AI Client                 ║"
    Write-Host "╚════════════════════════════════════════════════════════════╝"
    Write-Host ""
    
    if ([string]::IsNullOrEmpty($Token)) {
        Write-ColorOutput "No token provided. Limited functionality available." "Warning"
        Write-Host "   Use: `$env:THESIS_PLATFORM_TOKEN='your-token'"
        Write-Host ""
    }
    
    while ($true) {
        Write-Host ""
        Write-Host "Available Commands:"
        Write-Host "  1. List Models"
        Write-Host "  2. List Applications"
        Write-Host "  3. Get Statistics"
        Write-Host "  4. Health Check"
        Write-Host "  5. Verify Token"
        Write-Host "  q. Quit"
        Write-Host ""
        
        $choice = Read-Host "Enter command"
        Write-Host ""
        
        switch ($choice) {
            "1" { Get-Models }
            "2" { Get-Applications }
            "3" { Get-Stats }
            "4" { Get-Health }
            "5" { Test-Token }
            "q" { Write-ColorOutput "Goodbye!" "Success"; exit 0 }
            default { Write-ColorOutput "Invalid choice. Try again." "Error" }
        }
    }
}

# Main execution
if ($Help) {
    Show-Usage
}

switch ($Command.ToLower()) {
    "get-token" { Get-Token }
    "list-models" { Get-Models }
    "list-apps" { Get-Applications }
    "stats" { Get-Stats }
    "health" { Get-Health }
    "verify" { Test-Token }
    "generate" { New-Application }
    "interactive" { Start-Interactive }
    "" { Show-Usage }
    default {
        Write-ColorOutput "Unknown command: $Command" "Error"
        Write-Host "Use -Help for usage information"
        exit 1
    }
}
