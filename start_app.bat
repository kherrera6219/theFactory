@echo off
echo ==============================================
echo   Starting Mission Control Application Stack  
echo ==============================================
echo.

echo [1/2] Starting backend services via Docker...
where make >nul 2>nul
if not errorlevel 1 (
    call make up
) else (
    echo GNU Make was not found on PATH; using the Windows fallback.
    if not defined PGBOUNCER_HOST_PORT (
        echo PGBOUNCER_HOST_PORT was not set; using localhost port 5434 to avoid common PostgreSQL conflicts.
        set "PGBOUNCER_HOST_PORT=5434"
    )
    python scripts\check_env.py
    if errorlevel 1 goto backend_failed
    powershell -ExecutionPolicy Bypass -File scripts\generate_dev_tls_certs.ps1
    if errorlevel 1 goto backend_failed
    docker compose --env-file .env -f deploy\docker-compose.yaml up -d --build
)
if errorlevel 1 goto backend_failed
echo.

if /I "%~1"=="--backend-only" (
    echo Backend services started successfully.
    exit /b 0
)

echo [2/2] Starting Mission Control UI...
cd apps\mission-control

:: Build and start Mission Control in production mode so this script mirrors the
:: production image (Next.js standalone output). Pass --dev as the first arg to
:: start_app.bat to fall back to the hot-reloading dev server.
if /I "%~1"=="--dev" (
    start "Mission Control UI (dev)" cmd /k "echo Starting Next.js Dev Server... && npm run tokens:sync && npx next dev -p 3000"
) else (
    start "Mission Control UI" cmd /k "echo Building Next.js production bundle... && npm run build && echo Starting production server... && npm run start"
)

echo.
echo Application stack is starting up!
echo The Docker UI is available at http://localhost:3100.
echo The local UI window will be available at http://localhost:3000 shortly.
echo.
echo You can safely close this window. The UI will keep running in the new window.
echo Run stop_app.bat to spin down the backend services later.
pause
exit /b 0

:backend_failed
echo.
echo ERROR: Backend services failed to start. Mission Control UI was not launched.
echo Check Docker Desktop is running, then run start_app.bat again.
echo.
pause
exit /b 1
