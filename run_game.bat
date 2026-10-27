@echo off
setlocal
cd /d "%~dp0"

rem Keep Python/Qt temporary files inside the project instead of %TEMP% on C:
set "TMP=%~dp0.tmp"
set "TEMP=%~dp0.tmp"
set "XDG_CACHE_HOME=%~dp0.cache"
if not exist "%TMP%" mkdir "%TMP%"
if not exist "%XDG_CACHE_HOME%" mkdir "%XDG_CACHE_HOME%"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv not found. Run install_deps.bat first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" main.py
if errorlevel 1 pause
