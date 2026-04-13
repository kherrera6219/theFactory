@echo off
:: theFactory — double-click launcher
:: Delegates all logic to Launch-TheFactory.ps1
::
:: Usage:
::   Double-click this file            → start condensed stack
::   Launch-TheFactory.bat /full       → start full-dedicated-agents topology
::   Launch-TheFactory.bat /down       → stop and remove the stack
::
setlocal

set "SCRIPT=%~dp0Launch-TheFactory.ps1"
set "ARGS="

if /i "%1"=="/full" set "ARGS=-FullDedicated"
if /i "%1"=="/down" set "ARGS=-Down"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %ARGS%

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  Launch failed. See the output above for details.
    echo  Press any key to close...
    pause >nul
)
endlocal
