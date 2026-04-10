<#
.SYNOPSIS
    Activate the TestScripts Python venv in PowerShell.

.DESCRIPTION
    Usage (must dot-source to affect current session):
        . .\TestScripts\activate_venv.ps1

    Or from within TestScripts directory:
        . .\activate_venv.ps1

.EXAMPLE
    . .\TestScripts\activate_venv.ps1
    python test_pixel_stats.py capture.rdc
#>

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $ScriptDir ".venv"
$ActivateScript = Join-Path $VenvDir "Scripts\Activate.ps1"

if (-not (Test-Path $VenvDir)) {
    Write-Host "[ERROR] venv not found at: $VenvDir" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Please run setup_venv first:" -ForegroundColor Yellow
    Write-Host "    .\TestScripts\setup_venv.ps1" -ForegroundColor Cyan
    return
}

if (-not (Test-Path $ActivateScript)) {
    Write-Host "[ERROR] Activate.ps1 not found at: $ActivateScript" -ForegroundColor Red
    Write-Host "  The venv may be corrupted. Re-run setup_venv.ps1 -Force" -ForegroundColor Yellow
    return
}

# Activate the venv
& $ActivateScript

Write-Host "[INFO] venv activated." -ForegroundColor Green
python --version
