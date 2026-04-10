@echo off
setlocal enabledelayedexpansion

REM ============================================
REM  RenderDoc TestScripts - venv Setup (batch)
REM ============================================
REM
REM This script:
REM   1. Detects the required Python version from pythonXY.dll in x64\Release
REM   2. Locates the matching Python interpreter
REM   3. Creates a venv in TestScripts\.venv
REM
REM Usage:
REM   TestScripts\setup_venv.bat
REM   TestScripts\setup_venv.bat --force

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
set "RD_DIR=%PROJECT_ROOT%\x64\Release"
set "VENV_DIR=%SCRIPT_DIR%.venv"
set "FORCE=0"

REM Parse arguments
if /i "%~1"=="--force" set "FORCE=1"
if /i "%~1"=="-f" set "FORCE=1"

echo ============================================
echo   RenderDoc TestScripts - venv Setup
echo ============================================
echo.

REM --- Step 1: Detect required Python version ---
echo [1/4] Detecting required Python version...

if not exist "%RD_DIR%" (
    echo [ERROR] RenderDoc directory not found: %RD_DIR%
    echo   Build the project first.
    exit /b 1
)

set "REQ_MAJOR="
set "REQ_MINOR="

for %%f in ("%RD_DIR%\python[0-9][0-9].dll") do (
    set "DLLNAME=%%~nf"
)

REM Fallback: iterate to find pythonXY.dll
if not defined DLLNAME (
    for %%f in ("%RD_DIR%\python*.dll") do (
        set "CANDIDATE=%%~nf"
        REM Filter: name must be pythonXY (7-8 chars, not python3 or pythonXY_d)
        echo !CANDIDATE! | findstr /r "^python[0-9][0-9]$" >nul 2>&1
        if !errorlevel! equ 0 (
            set "DLLNAME=!CANDIDATE!"
        )
    )
)

if not defined DLLNAME (
    echo [ERROR] No pythonXY.dll found in: %RD_DIR%
    exit /b 1
)

REM Extract version digits from "pythonXY"
set "DLLNAME_STRIPPED=%DLLNAME:python=%"
set "REQ_MAJOR=%DLLNAME_STRIPPED:~0,1%"
set "REQ_MINOR=%DLLNAME_STRIPPED:~1%"
set "REQ_VERSION=%REQ_MAJOR%.%REQ_MINOR%"

echo   Found %DLLNAME%.dll -^> requires Python %REQ_VERSION%

REM --- Step 2: Locate matching Python ---
echo.
echo [2/4] Locating Python %REQ_VERSION% interpreter...

set "PYTHON_EXE="

REM Method 1: py launcher
where py >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%i in ('py -%REQ_VERSION% -c "import sys; print(sys.executable)" 2^>nul') do (
        set "PYTHON_EXE=%%i"
    )
    if defined PYTHON_EXE (
        echo   Found via py launcher: !PYTHON_EXE!
    )
)

REM Method 2: Common paths
if not defined PYTHON_EXE (
    for %%p in (
        "C:\Python%REQ_MAJOR%%REQ_MINOR%\python.exe"
        "C:\Program Files\Python%REQ_MAJOR%%REQ_MINOR%\python.exe"
        "C:\Program Files (x86)\Python%REQ_MAJOR%%REQ_MINOR%\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python%REQ_MAJOR%%REQ_MINOR%\python.exe"
    ) do (
        if exist %%p (
            if not defined PYTHON_EXE (
                set "PYTHON_EXE=%%~p"
                echo   Found at: !PYTHON_EXE!
            )
        )
    )
)

if not defined PYTHON_EXE (
    echo [ERROR] Python %REQ_VERSION% not found!
    echo.
    echo   Please install Python %REQ_VERSION% from:
    echo     https://www.python.org/downloads/
    echo.
    echo   Or create venv manually:
    echo     ^<path-to-python%REQ_VERSION%^>\python.exe -m venv "%VENV_DIR%"
    exit /b 1
)

echo   Version: Python %REQ_VERSION%

REM --- Step 3: Create venv ---
echo.
echo [3/4] Creating virtual environment...

if exist "%VENV_DIR%" (
    if "%FORCE%"=="1" (
        echo   Removing existing venv...
        rmdir /s /q "%VENV_DIR%"
    ) else (
        echo   venv already exists at: %VENV_DIR%
        echo   Use --force to recreate.
        goto :summary
    )
)

echo   Creating venv at: %VENV_DIR%
"%PYTHON_EXE%" -m venv "%VENV_DIR%"
if %errorlevel% neq 0 (
    echo [ERROR] Failed to create virtual environment.
    exit /b 1
)
echo   venv created successfully.

:summary
REM --- Step 4: Summary ---
echo.
echo [4/4] Setup complete!
echo.
echo ============================================
echo   Virtual Environment Ready
echo ============================================
echo.
echo   Location : %VENV_DIR%
echo   Python   : %REQ_VERSION%
echo.
echo   To activate (cmd.exe):
echo     %VENV_DIR%\Scripts\activate.bat
echo.
echo   To activate (PowerShell):
echo     %VENV_DIR%\Scripts\Activate.ps1
echo.
echo   Then run test scripts:
echo     python TestScripts\test_pixel_stats.py ^<your_capture.rdc^>
echo.
echo   To deactivate:
echo     deactivate
echo.

endlocal
