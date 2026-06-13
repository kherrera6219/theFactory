@echo off
cd /d "%~dp0"
set "CONDENSED_MODE=false"
set "BACKEND_ONLY=false"
set "DEV_MODE=false"
for %%a in (%*) do (
    if /I "%%~a"=="--condensed" set "CONDENSED_MODE=true"
    if /I "%%~a"=="--backend-only" set "BACKEND_ONLY=true"
    if /I "%%~a"=="--dev" set "DEV_MODE=true"
)

echo ==============================================
echo   Starting Mission Control Application Stack  
echo ==============================================
echo.

echo [1/2] Starting backend services via Docker...
where make >nul 2>nul
if not errorlevel 1 (
    if "%CONDENSED_MODE%"=="true" (
        call make up-condensed
    ) else (
        call make up
    )
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
    if "%CONDENSED_MODE%"=="true" (
        docker compose --env-file .env -f deploy\docker-compose.yaml up -d --build
    ) else (
        docker compose --env-file .env -f deploy\docker-compose.yaml -f deploy\docker-compose.full-dedicated-agents.yaml --profile full-dedicated-agents up -d --build redis postgres pgbouncer qdrant minio milvus neo4j jaeger orchestrator api-gateway protocol-bus-mcp audit-worker dashboard mission-control pod-a-dedicated-mgr-worker pod-b-dedicated-mgr-worker pod-c-dedicated-mgr-worker pod-d-dedicated-mgr-worker agent-01-pm agent-02-ceo agent-03-broker agent-04-accountant agent-05-security agent-06-is agent-07-vc agent-08-compliance agent-09-hw agent-10-tester agent-11-deploy agent-13-poda-audit agent-19-podb-audit agent-25-podc-audit agent-31-podd-audit agent-14-python agent-15-javascript agent-16-ruby agent-17-php agent-20-c agent-21-cpp agent-22-rust agent-23-zig agent-36-go agent-26-java agent-27-csharp agent-28-scala agent-29-kotlin agent-32-matlab agent-33-r agent-34-julia agent-35-mathematica agent-37-haskell agent-38-ocaml agent-39-depabs agent-40-testdata agent-41-rqca
    )
)
if errorlevel 1 goto backend_failed
echo.

if "%BACKEND_ONLY%"=="true" (
    echo Backend services started successfully.
    exit /b 0
)

echo [2/2] Starting Mission Control UI...
cd apps\mission-control

:: Build and start Mission Control in production mode so this script mirrors the
:: production image (Next.js standalone output). Pass --dev to
:: start_app.bat to fall back to the hot-reloading dev server.
if "%DEV_MODE%"=="true" (
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
