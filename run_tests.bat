@echo off
setlocal
cd /d "%~dp0"

rem Keep pytest temp files and pip cache inside the project.
set "TMP=%~dp0.tmp"
set "TEMP=%~dp0.tmp"
set "PIP_CACHE_DIR=%~dp0.cache\pip"
set "XDG_CACHE_HOME=%~dp0.cache"
if not exist "%TMP%" mkdir "%TMP%"
if not exist "%PIP_CACHE_DIR%" mkdir "%PIP_CACHE_DIR%"
if not exist "%XDG_CACHE_HOME%" mkdir "%XDG_CACHE_HOME%"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv not found. Run install_deps.bat first.
    pause
    exit /b 1
)

if "%~1"=="" (
    ".venv\Scripts\python.exe" -m pytest tests -q
) else (
    ".venv\Scripts\python.exe" -m pytest %* -q
)
if errorlevel 1 pause
