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

:: Build and start Mission Control in production mode so this script mirrors the
:: production image (Next.js standalone output). Pass --dev as the first arg to
:: start_app.bat to fall back to the hot-reloading dev server.
if /I "%~1"=="--dev" (
    start "Mission Control UI (dev)" cmd /k "echo Starting Next.js Dev Server... && npm run dev"
) else (
    start "Mission Control UI" cmd /k "echo Building Next.js production bundle... && npm run build && echo Starting production server... && npm run start"
)

echo.
echo Application stack is starting up!
echo The UI will be available at http://localhost:3000 shortly.
echo.
echo You can safely close this window. The UI will keep running in the new window.
echo Run stop_app.bat to spin down the backend services later.
pause
