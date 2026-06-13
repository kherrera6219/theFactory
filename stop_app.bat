@echo off
cd /d "%~dp0"
setlocal enabledelayedexpansion

echo ==============================================
echo   Stopping Mission Control Application Stack  
echo ==============================================
echo.

:: Use the Python cleanup system for a thorough and verified stop
python scripts\force_stop.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo WARNING: Some processes could not be cleared automatically.
    echo Please check for any hanging "cmd" or "node" windows and close them manually.
) else (
    echo.
    echo Application stack stopped and verified.
)

echo.
pause
