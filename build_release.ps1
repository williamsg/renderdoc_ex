# build_release.ps1 - Build RenderDoc Release (x64) on Windows
param(
    [string]$Configuration = "Release",
    [string]$Platform = "x64",
    [string]$PlatformToolset = "v143",
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$SolutionFile = Join-Path $ScriptDir "renderdoc.sln"
$LogFile = Join-Path $ScriptDir "build_release.log"
$ErrLogFile = Join-Path $ScriptDir "build_release_err.log"
$OutputDir = Join-Path $ScriptDir "$Platform\$Configuration"

# Find MSBuild via vswhere
function Find-MSBuild {
    $vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    if (Test-Path $vswhere) {
        $msbuild = & $vswhere -latest -requires Microsoft.Component.MSBuild -find "MSBuild\**\Bin\MSBuild.exe" | Select-Object -First 1
        if ($msbuild -and (Test-Path $msbuild)) {
            return $msbuild
        }
    }
    # Fallback: try well-known path
    $fallback = "C:\Program Files\Microsoft Visual Studio\2022\Professional\MSBuild\Current\Bin\MSBuild.exe"
    if (Test-Path $fallback) {
        return $fallback
    }
    return $null
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  RenderDoc Release Build Script" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Configuration:    $Configuration"
Write-Host "Platform:         $Platform"
Write-Host "PlatformToolset:  $PlatformToolset"
Write-Host "Solution:         $SolutionFile"
Write-Host ""

# Verify solution file exists
if (-not (Test-Path $SolutionFile)) {
    Write-Host "ERROR: Solution file not found: $SolutionFile" -ForegroundColor Red
    exit 1
}

# Find MSBuild
$MSBuild = Find-MSBuild
if (-not $MSBuild) {
    Write-Host "ERROR: MSBuild.exe not found. Please install Visual Studio with C++ workload." -ForegroundColor Red
    exit 1
}
Write-Host "MSBuild:          $MSBuild"
Write-Host ""

# Build arguments
$BuildArgs = @(
    "`"$SolutionFile`""
    "/m"
    "/p:Configuration=$Configuration"
    "/p:Platform=$Platform"
    "/p:PlatformToolset=$PlatformToolset"
)

if ($Clean) {
    Write-Host "Cleaning..." -ForegroundColor Yellow
    $CleanArgs = $BuildArgs + @("/t:Clean")
    & $MSBuild $CleanArgs 2>&1 | Out-Null
    Write-Host "Clean completed." -ForegroundColor Green
    Write-Host ""
}

# Start build
Write-Host "Building... (output logged to $LogFile)" -ForegroundColor Yellow
$StartTime = Get-Date

$process = Start-Process -FilePath $MSBuild `
    -ArgumentList ($BuildArgs -join " ") `
    -WorkingDirectory $ScriptDir `
    -RedirectStandardOutput $LogFile `
    -RedirectStandardError $ErrLogFile `
    -NoNewWindow -PassThru

# Wait for build to complete with progress indicator
$spinner = @('|', '/', '-', '\')
$i = 0
while (-not $process.HasExited) {
    $elapsed = (Get-Date) - $StartTime
    $spinChar = $spinner[$i % 4]
    Write-Host "`r  $spinChar Building... [$([math]::Floor($elapsed.TotalSeconds))s elapsed]" -NoNewline
    Start-Sleep -Milliseconds 500
    $i++
}
Write-Host "`r                                                  " -NoNewline
Write-Host ""

$Duration = (Get-Date) - $StartTime
$ExitCode = $process.ExitCode

# Parse build summary from log
$LogContent = Get-Content $LogFile -Tail 20 -ErrorAction SilentlyContinue
$SummaryLine = $LogContent | Where-Object { $_ -match "Build succeeded|Build FAILED" } | Select-Object -Last 1
$WarningLine = $LogContent | Where-Object { $_ -match "\d+ Warning\(s\)" } | Select-Object -Last 1
$ErrorLine = $LogContent | Where-Object { $_ -match "\d+ Error\(s\)" } | Select-Object -Last 1

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Build Result" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

if ($ExitCode -eq 0) {
    Write-Host "  Status:   BUILD SUCCEEDED" -ForegroundColor Green
} else {
    Write-Host "  Status:   BUILD FAILED (exit code: $ExitCode)" -ForegroundColor Red
}

Write-Host "  Duration: $([math]::Floor($Duration.TotalMinutes))m $($Duration.Seconds)s"
if ($WarningLine) { Write-Host "  $($WarningLine.Trim())" -ForegroundColor Yellow }
if ($ErrorLine)   { Write-Host "  $($ErrorLine.Trim())" -ForegroundColor $(if ($ExitCode -ne 0) { "Red" } else { "White" }) }
Write-Host ""

if ($ExitCode -eq 0 -and (Test-Path $OutputDir)) {
    Write-Host "  Output: $OutputDir" -ForegroundColor Green
    Write-Host ""
    $keyFiles = @("renderdoc.dll", "qrenderdoc.exe", "renderdoccmd.exe", "renderdocshim64.dll")
    foreach ($f in $keyFiles) {
        $filePath = Join-Path $OutputDir $f
        if (Test-Path $filePath) {
            $size = (Get-Item $filePath).Length
            $sizeStr = if ($size -gt 1MB) { "{0:N1} MB" -f ($size / 1MB) } else { "{0:N0} KB" -f ($size / 1KB) }
            Write-Host "    $f  ($sizeStr)"
        }
    }
    Write-Host ""
} elseif ($ExitCode -ne 0) {
    Write-Host "  Check build log for details:" -ForegroundColor Yellow
    Write-Host "    $LogFile"
    Write-Host "    $ErrLogFile"
    # Show last few error lines
    $ErrContent = Get-Content $ErrLogFile -ErrorAction SilentlyContinue
    if ($ErrContent) {
        Write-Host ""
        Write-Host "  Errors:" -ForegroundColor Red
        $ErrContent | Select-Object -Last 10 | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
    }
    Write-Host ""
}

exit $ExitCode