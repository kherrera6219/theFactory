@echo off
echo ==============================================
echo   Starting Mission Control Application Stack  
echo ==============================================
echo.

echo [1/2] Starting backend services via Docker...
call make up
echo.

echo [2/2] Starting Mission Control UI...
cd apps\mission-control

:: Start the Next.js dev server in a new window so it keeps running
start "Mission Control UI" cmd /k "echo Starting Next.js Dev Server... && npm run dev"

echo.
echo Application stack is starting up!
echo The UI will be available at http://localhost:3000 shortly.
echo.
echo You can safely close this window. The UI will keep running in the new window.
echo Run stop_app.bat to spin down the backend services later.
pause
