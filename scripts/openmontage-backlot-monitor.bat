@echo off
setlocal enabledelayedexpansion

set "PROJECT_DIR=G:\Hermes\OpenMontage"
set "PYTHON_EXE=%PROJECT_DIR%\.venv\Scripts\python.exe"
set "PORT=4750"
set "HEALTH_URL=http://127.0.0.1:%PORT%/api/health"

cd /d "%PROJECT_DIR%"

:restart
echo ==============================
echo STARTING OPENMONTAGE BACKLOT
echo ==============================
start "OPENMONTAGE BACKLOT" cmd /c "cd /d %PROJECT_DIR% && set PYTHONPATH= && \"%PYTHON_EXE%\" -m backlot serve --port %PORT%"

echo === WAIT FOR SERVER ===
:wait_server
timeout /t 5 /nobreak >nul
curl -fsS "%HEALTH_URL%" >nul 2>&1
if errorlevel 1 goto wait_server
echo === SERVER IS UP ===

:monitor
timeout /t 10 /nobreak >nul
curl -fsS "%HEALTH_URL%" >nul 2>&1
if errorlevel 1 (
    echo BACKLOT DOWN -> RESTART
    timeout /t 5 /nobreak >nul
    goto restart
)

goto monitor
