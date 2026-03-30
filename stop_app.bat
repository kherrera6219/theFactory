@echo off
echo ==============================================
echo   Stopping Mission Control Application Stack  
echo ==============================================
echo.

echo Stopping backend services and tearing down containers...
call make down

echo.
echo Backend services stopped successfully.
echo Note: If the UI window (Next.js) is still open, you can close it manually.
pause
