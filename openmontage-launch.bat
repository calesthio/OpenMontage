@echo off
setlocal
cd /d G:\Hermes\OpenMontage
set "PYTHONPATH=G:\Hermes\OpenMontage;%PYTHONPATH%"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m backlot open %*
) else (
  python -m backlot open %*
)
if errorlevel 1 (
  echo.
  echo OpenMontage failed to start.
  pause
)
endlocal
