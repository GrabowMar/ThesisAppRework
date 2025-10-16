#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Automated cleanup script for ThesisAppRework project
    
.DESCRIPTION
    Performs safe cleanup operations to remove redundant files and improve codebase health.
    All operations are logged and can be reviewed before permanent deletion.
    
.PARAMETER DryRun
    Show what would be cleaned without actually deleting anything
    
.PARAMETER CleanBytecode
    Clean Python bytecode files (__pycache__, *.pyc)
    
.PARAMETER ArchiveDocs
    Move docs/archive to separate location
    
.PARAMETER All
    Perform all cleanup operations
    
.EXAMPLE
    .\cleanup.ps1 -DryRun
    Show what would be cleaned
    
.EXAMPLE
    .\cleanup.ps1 -CleanBytecode
    Clean only Python bytecode files
    
.EXAMPLE
    .\cleanup.ps1 -All
    Perform all cleanup operations
#>

param(
    [switch]$DryRun,
    [switch]$CleanBytecode,
    [switch]$ArchiveDocs,
    [switch]$All
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

# Colors for output
function Write-Success { Write-Host $args -ForegroundColor Green }
function Write-Info { Write-Host $args -ForegroundColor Cyan }
function Write-Warning { Write-Host $args -ForegroundColor Yellow }
function Write-Error { Write-Host $args -ForegroundColor Red }

function Write-Banner {
    Write-Host "`n" + "="*80 -ForegroundColor Magenta
    Write-Host "  ThesisAppRework Cleanup Script" -ForegroundColor Magenta
    Write-Host "="*80 + "`n" -ForegroundColor Magenta
}

function Clean-Bytecode {
    Write-Info "`n🧹 Cleaning Python bytecode files..."
    
    $pycacheCount = 0
    $pycCount = 0
    $totalSize = 0
    
    # Find __pycache__ directories
    $pycacheDirs = Get-ChildItem -Path $ProjectRoot -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue
    $pycacheCount = ($pycacheDirs | Measure-Object).Count
    
    # Find .pyc files
    $pycFiles = Get-ChildItem -Path $ProjectRoot -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue
    $pycCount = ($pycFiles | Measure-Object).Count
    
    if ($pycFiles) {
        $totalSize = ($pycFiles | Measure-Object -Property Length -Sum).Sum
    }
    
    Write-Info "  Found: $pycacheCount __pycache__ directories"
    Write-Info "  Found: $pycCount .pyc files"
    Write-Info "  Total size: $([math]::Round($totalSize/1MB, 2)) MB"
    
    if ($DryRun) {
        Write-Warning "  [DRY RUN] Would delete $pycacheCount directories and $pycCount files"
        return
    }
    
    # Clean __pycache__
    if ($pycacheDirs) {
        Write-Info "  Removing __pycache__ directories..."
        $pycacheDirs | Remove-Item -Recurse -Force
        Write-Success "  ✓ Removed $pycacheCount __pycache__ directories"
    }
    
    # Clean .pyc files
    if ($pycFiles) {
        Write-Info "  Removing .pyc files..."
        $pycFiles | Remove-Item -Force -ErrorAction SilentlyContinue
        Write-Success "  ✓ Removed $pycCount .pyc files"
    }
    
    if (-not $pycacheDirs -and -not $pycFiles) {
        Write-Success "  ✓ No bytecode files found - already clean!"
    }
}

function Archive-Documentation {
    Write-Info "`n📚 Archiving old documentation..."
    
    $archiveDir = Join-Path $ProjectRoot "docs\archive"
    $archiveDestination = Join-Path $ProjectRoot "..\ThesisAppRework-docs-archive"
    
    if (-not (Test-Path $archiveDir)) {
        Write-Warning "  No archive directory found at: $archiveDir"
        return
    }
    
    $archiveFiles = Get-ChildItem -Path $archiveDir -File
    $fileCount = ($archiveFiles | Measure-Object).Count
    $totalSize = ($archiveFiles | Measure-Object -Property Length -Sum).Sum
    
    Write-Info "  Found: $fileCount files in docs/archive"
    Write-Info "  Total size: $([math]::Round($totalSize/1MB, 2)) MB"
    
    if ($DryRun) {
        Write-Warning "  [DRY RUN] Would move to: $archiveDestination"
        return
    }
    
    # Ask for confirmation
    Write-Warning "`n  ⚠️  This will move docs/archive to $archiveDestination"
    $response = Read-Host "  Continue? (y/N)"
    
    if ($response -ne 'y' -and $response -ne 'Y') {
        Write-Info "  Cancelled by user"
        return
    }
    
    # Create archive destination
    if (-not (Test-Path $archiveDestination)) {
        New-Item -ItemType Directory -Path $archiveDestination -Force | Out-Null
        Write-Info "  Created: $archiveDestination"
    }
    
    # Move archive directory
    Write-Info "  Moving archive directory..."
    Move-Item -Path $archiveDir -Destination $archiveDestination -Force
    Write-Success "  ✓ Moved $fileCount files to $archiveDestination"
    
    # Create README in new location
    $readmePath = Join-Path $archiveDestination "README.md"
    @"
# ThesisAppRework Documentation Archive

This directory contains archived documentation from the ThesisAppRework project.

**Archived on**: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

These files are kept for historical reference but are no longer actively maintained.
For current documentation, see the main project repository.

## Contents

- Original location: `docs/archive/`
- Files archived: $fileCount
- Total size: $([math]::Round($totalSize/1MB, 2)) MB

## Files

"@ | Out-File -FilePath $readmePath -Encoding UTF8
    
    Get-ChildItem -Path (Join-Path $archiveDestination "archive") -File | ForEach-Object {
        "- $($_.Name)" | Out-File -FilePath $readmePath -Append -Encoding UTF8
    }
    
    Write-Success "  ✓ Created README in archive location"
}

function Update-GitIgnore {
    Write-Info "`n📝 Updating .gitignore..."
    
    $gitignorePath = Join-Path $ProjectRoot ".gitignore"
    $patterns = @(
        "__pycache__/",
        "*.py[cod]",
        "*$py.class",
        "*.so",
        ".Python"
    )
    
    if (-not (Test-Path $gitignorePath)) {
        Write-Warning "  No .gitignore found - creating one"
        $patterns | Out-File -FilePath $gitignorePath -Encoding UTF8
        Write-Success "  ✓ Created .gitignore with Python patterns"
        return
    }
    
    $gitignoreContent = Get-Content $gitignorePath -Raw
    $added = @()
    
    foreach ($pattern in $patterns) {
        if ($gitignoreContent -notmatch [regex]::Escape($pattern)) {
            if (-not $DryRun) {
                Add-Content -Path $gitignorePath -Value $pattern -Encoding UTF8
            }
            $added += $pattern
        }
    }
    
    if ($added.Count -gt 0) {
        if ($DryRun) {
            Write-Warning "  [DRY RUN] Would add: $($added -join ', ')"
        } else {
            Write-Success "  ✓ Added $($added.Count) patterns to .gitignore"
        }
    } else {
        Write-Success "  ✓ .gitignore already up to date"
    }
}

function Show-Summary {
    Write-Info "`n📊 Cleanup Summary"
    Write-Host "="*80 -ForegroundColor Cyan
    
    # Count current state
    $pycacheCount = (Get-ChildItem -Path $ProjectRoot -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Measure-Object).Count
    $pycCount = (Get-ChildItem -Path $ProjectRoot -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue | Measure-Object).Count
    $archiveExists = Test-Path (Join-Path $ProjectRoot "docs\archive")
    
    Write-Info "  __pycache__ directories: $pycacheCount"
    Write-Info "  .pyc files: $pycCount"
    Write-Info "  docs/archive exists: $archiveExists"
    
    if ($pycacheCount -eq 0 -and $pycCount -eq 0 -and -not $archiveExists) {
        Write-Success "`n  ✅ Project is clean!"
    } else {
        Write-Warning "`n  ⚠️  Cleanup recommended"
        Write-Info "  Run: .\cleanup.ps1 -All"
    }
    
    Write-Host "="*80 -ForegroundColor Cyan
}

# Main execution
Write-Banner

if ($DryRun) {
    Write-Warning "🔍 DRY RUN MODE - No changes will be made`n"
}

if ($All -or (-not $CleanBytecode -and -not $ArchiveDocs -and -not $DryRun)) {
    # Show what we'll do
    Write-Info "This script will perform the following cleanup operations:`n"
    Write-Info "  1. Clean Python bytecode files (__pycache__, *.pyc)"
    Write-Info "  2. Update .gitignore"
    if (-not $DryRun) {
        Write-Info "  3. Optionally archive old documentation`n"
    }
    
    if (-not $DryRun) {
        $response = Read-Host "Continue? (y/N)"
        if ($response -ne 'y' -and $response -ne 'Y') {
            Write-Info "Cancelled by user"
            exit 0
        }
    }
}

# Run requested operations
if ($All -or $CleanBytecode) {
    Clean-Bytecode
}

if ($All -or $CleanBytecode) {
    Update-GitIgnore
}

if ($All -or $ArchiveDocs) {
    Archive-Documentation
}

# Show final summary
if (-not $DryRun) {
    Show-Summary
}

Write-Info "`n✨ Cleanup complete!"
Write-Host ""
