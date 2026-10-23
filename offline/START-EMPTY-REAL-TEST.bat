@echo off
rem Starts the offline copy WITHOUT demo data: an empty school with two-step sign-in, like the real server.
rem Use it on a fresh install or after RESET-ALL-DATA.bat. Do not mix demo data and real test data.
cd /d "%~dp0.."
set TASEMS_DEMO=False
docker compose -f docker-compose.offline.yml up -d --build
if errorlevel 1 (
  pause
  exit /b 1
)
echo In one minute it opens at http://localhost:8000 . Make the master login first with MAKE-MASTER-LOGIN.bat
timeout /t 60 >nul
start http://localhost:8000
pause
