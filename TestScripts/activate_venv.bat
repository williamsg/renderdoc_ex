@echo off
REM ============================================
REM  Activate the TestScripts Python venv
REM ============================================
REM
REM For cmd.exe:
REM   call TestScripts\activate_venv.bat
REM
REM For PowerShell:
REM   . .\TestScripts\activate_venv.ps1
REM
REM WARNING: This .bat file only works in cmd.exe.
REM          In PowerShell, use activate_venv.ps1 instead.
REM

REM Detect if running inside PowerShell (bat won't persist env in PS)
if defined PSModulePath (
    echo [WARNING] You appear to be running in PowerShell.
    echo   .bat activation does NOT persist in PowerShell sessions.
    echo.
    echo   Use the PowerShell script instead:
    echo     . .\TestScripts\activate_venv.ps1
    echo.
    echo   Continuing anyway for cmd.exe compatibility...
    echo.
)

set "SCRIPT_DIR=%~dp0"
set "VENV_DIR=%SCRIPT_DIR%.venv"
set "ACTIVATE=%VENV_DIR%\Scripts\activate.bat"

if not exist "%VENV_DIR%" (
    echo [ERROR] venv not found at: %VENV_DIR%
    echo.
    echo   Please run setup_venv first:
    echo     TestScripts\setup_venv.bat
    echo     -- or --
    echo     powershell -ExecutionPolicy Bypass -File TestScripts\setup_venv.ps1
    exit /b 1
)

if not exist "%ACTIVATE%" (
    echo [ERROR] activate.bat not found at: %ACTIVATE%
    echo   The venv may be corrupted. Re-run setup_venv with --force.
    exit /b 1
)

call "%ACTIVATE%"
echo [INFO] venv activated. Python:
python --version
