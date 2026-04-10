<#
.SYNOPSIS
    Set up a Python virtual environment matching the renderdoc.pyd requirement.

.DESCRIPTION
    This script:
    1. Detects the required Python version from pythonXY.dll in x64/Release
    2. Locates the matching Python interpreter via py launcher or common paths
    3. Creates a venv in TestScripts/.venv
    4. Prints activation instructions

.PARAMETER RdDir
    Path to the directory containing renderdoc.pyd. Defaults to <project>/x64/Release.

.PARAMETER VenvDir
    Path for the virtual environment. Defaults to TestScripts/.venv.

.PARAMETER Force
    If set, recreates the venv even if it already exists.

.EXAMPLE
    .\TestScripts\setup_venv.ps1
    .\TestScripts\setup_venv.ps1 -Force
    .\TestScripts\setup_venv.ps1 -RdDir "D:\custom_build\x64\Release"
#>

param(
    [string]$RdDir = "",
    [string]$VenvDir = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

# --- Defaults ---
if (-not $RdDir) {
    $RdDir = Join-Path $ProjectRoot "x64\Release"
}
if (-not $VenvDir) {
    $VenvDir = Join-Path $ScriptDir ".venv"
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  RenderDoc TestScripts - venv Setup" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# --- Step 1: Detect required Python version from pythonXY.dll ---
Write-Host "[1/4] Detecting required Python version..." -ForegroundColor Yellow

if (-not (Test-Path $RdDir)) {
    Write-Host "[ERROR] RenderDoc directory not found: $RdDir" -ForegroundColor Red
    Write-Host "  Build the project first, or specify -RdDir parameter." -ForegroundColor Red
    exit 1
}

$pythonDlls = Get-ChildItem -Path $RdDir -Filter "python*.dll" -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match "^python\d\d\.dll$" }
if (-not $pythonDlls -or @($pythonDlls).Count -eq 0) {
    Write-Host "[ERROR] No pythonXY.dll found in: $RdDir" -ForegroundColor Red
    Write-Host "  Cannot determine required Python version." -ForegroundColor Red
    exit 1
}

$dllName = @($pythonDlls)[0].Name
if ($dllName -match "python(\d)(\d+)\.dll") {
    $reqMajor = $Matches[1]
    $reqMinor = $Matches[2]
} else {
    Write-Host "[ERROR] Cannot parse Python version from: $dllName" -ForegroundColor Red
    exit 1
}

$reqVersion = "$reqMajor.$reqMinor"
Write-Host "  Found $dllName -> requires Python $reqVersion" -ForegroundColor Green

# --- Step 2: Locate the matching Python interpreter ---
Write-Host ""
Write-Host "[2/4] Locating Python $reqVersion interpreter..." -ForegroundColor Yellow

$pythonExe = $null

# Method 1: Try py launcher
try {
    $pyOutput = & py "-$reqVersion" -c "import sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -eq 0 -and $pyOutput) {
        $pythonExe = $pyOutput.Trim()
        Write-Host "  Found via py launcher: $pythonExe" -ForegroundColor Green
    }
} catch {
    # py launcher not available
}

# Method 2: Search common installation paths
if (-not $pythonExe) {
    $searchPaths = @(
        "C:\Python$reqMajor$reqMinor\python.exe",
        "C:\Python\$reqVersion\python.exe",
        "C:\Program Files\Python$reqMajor$reqMinor\python.exe",
        "C:\Program Files (x86)\Python$reqMajor$reqMinor\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python$reqMajor$reqMinor\python.exe",
        "$env:APPDATA\Python\Python$reqMajor$reqMinor\python.exe"
    )

    foreach ($p in $searchPaths) {
        if (Test-Path $p) {
            $pythonExe = $p
            Write-Host "  Found at common path: $pythonExe" -ForegroundColor Green
            break
        }
    }
}

# Method 3: Try plain 'python' and check version
if (-not $pythonExe) {
    try {
        $verOutput = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}'); print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $verOutput) {
            $lines = $verOutput -split "`n"
            if ($lines[0].Trim() -eq $reqVersion) {
                $pythonExe = $lines[1].Trim()
                Write-Host "  Found via PATH: $pythonExe" -ForegroundColor Green
            }
        }
    } catch {}
}

if (-not $pythonExe) {
    Write-Host "[ERROR] Python $reqVersion not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Please install Python $reqVersion from:" -ForegroundColor Red
    Write-Host "    https://www.python.org/downloads/release/python-$reqMajor${reqMinor}0/" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Or specify the path manually and create venv:" -ForegroundColor Red
    Write-Host "    & `"<path-to-python$reqVersion>\python.exe`" -m venv `"$VenvDir`"" -ForegroundColor Cyan
    exit 1
}

# Verify the found Python is the correct version
$verCheck = & "$pythonExe" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
if ($verCheck.Trim() -ne $reqVersion) {
    Write-Host "[ERROR] Python at $pythonExe reports version $verCheck, expected $reqVersion" -ForegroundColor Red
    exit 1
}

# Verify bitness matches (x64 build needs 64-bit Python)
$bitnessCheck = & "$pythonExe" -c "import struct; print(struct.calcsize('P') * 8)" 2>$null
if ($bitnessCheck.Trim() -ne "64") {
    Write-Host "[WARNING] Python at $pythonExe is $($bitnessCheck.Trim())-bit, but x64 build needs 64-bit Python." -ForegroundColor Red
    Write-Host "  Please install 64-bit Python $reqVersion." -ForegroundColor Red
    exit 1
}

Write-Host "  Version verified: Python $reqVersion (64-bit)" -ForegroundColor Green

# --- Step 3: Create venv ---
Write-Host ""
Write-Host "[3/4] Creating virtual environment..." -ForegroundColor Yellow

$skipCreate = $false
if (Test-Path $VenvDir) {
    if ($Force) {
        Write-Host "  Removing existing venv (--Force)..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force $VenvDir
    } else {
        Write-Host "  venv already exists at: $VenvDir" -ForegroundColor Green
        Write-Host "  Use -Force to recreate it." -ForegroundColor Yellow

        # Still verify it's the right version
        $venvPython = Join-Path $VenvDir "Scripts\python.exe"
        if (Test-Path $venvPython) {
            $venvVer = & "$venvPython" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($venvVer.Trim() -ne $reqVersion) {
                Write-Host "  [WARNING] Existing venv uses Python $venvVer, but $reqVersion is required!" -ForegroundColor Red
                Write-Host "  Run with -Force to recreate." -ForegroundColor Red
                exit 1
            }
        }

        # Skip to step 4
        $skipCreate = $true
    }
}

if (-not $skipCreate) {
    Write-Host "  Creating venv at: $VenvDir"
    & "$pythonExe" -m venv "$VenvDir"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to create virtual environment." -ForegroundColor Red
        exit 1
    }
    Write-Host "  venv created successfully." -ForegroundColor Green
}

# --- Step 4: Summary & activation instructions ---
Write-Host ""
Write-Host "[4/4] Setup complete!" -ForegroundColor Yellow
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Virtual Environment Ready" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Location : $VenvDir" -ForegroundColor White
Write-Host "  Python   : $reqVersion (64-bit)" -ForegroundColor White
Write-Host ""
Write-Host "  To activate (PowerShell):" -ForegroundColor Yellow
Write-Host "    $VenvDir\Scripts\Activate.ps1" -ForegroundColor Cyan
Write-Host ""
Write-Host "  To activate (cmd.exe):" -ForegroundColor Yellow
Write-Host "    $VenvDir\Scripts\activate.bat" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Then run test scripts:" -ForegroundColor Yellow
Write-Host "    python TestScripts\test_pixel_stats.py <your_capture.rdc>" -ForegroundColor Cyan
Write-Host "    python TestScripts\test_basic_info.py <your_capture.rdc>" -ForegroundColor Cyan
Write-Host ""
Write-Host "  To deactivate:" -ForegroundColor Yellow
Write-Host "    deactivate" -ForegroundColor Cyan
Write-Host ""
