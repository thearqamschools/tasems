@echo off
rem Stops TASEMS. All data stays on this computer and comes back with the next start.
cd /d "%~dp0.."
docker compose -f docker-compose.offline.yml stop
echo TASEMS stopped. Data is kept.
pause
