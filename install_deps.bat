@echo off
setlocal
cd /d "%~dp0"

rem Keep pip download/build cache and temporary files inside the project.
set "TMP=%~dp0.tmp"
set "TEMP=%~dp0.tmp"
set "PIP_CACHE_DIR=%~dp0.cache\pip"
set "XDG_CACHE_HOME=%~dp0.cache"
if not exist "%TMP%" mkdir "%TMP%"
if not exist "%PIP_CACHE_DIR%" mkdir "%PIP_CACHE_DIR%"
if not exist "%XDG_CACHE_HOME%" mkdir "%XDG_CACHE_HOME%"

if not exist ".venv\Scripts\python.exe" (
    echo Creating .venv with Python 3.10...
    py -3.10 -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Could not create .venv. Install Python 3.10 first.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    pause
    exit /b 1
)

echo.
echo Dependencies installed. Double-click run_game.bat to start.
pause
