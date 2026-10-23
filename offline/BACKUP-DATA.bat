@echo off
rem Saves a copy of all TASEMS data in the backups folder. Keep it safe: it holds the school's data.
cd /d "%~dp0.."
if not exist backups mkdir backups
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmm"') do set STAMP=%%i
docker compose -f docker-compose.offline.yml exec -T db pg_dump -U postgres -d tasems -Fc > "backups\tasems-%STAMP%.dump"
echo Saved backups\tasems-%STAMP%.dump
pause
