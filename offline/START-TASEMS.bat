@echo off
rem Starts the offline TASEMS test copy with fictional demo data (no two-step sign-in).
rem The first start takes 10-20 minutes and needs internet once; after that no internet is needed.
cd /d "%~dp0.."
set TASEMS_DEMO=True
docker compose -f docker-compose.offline.yml up -d --build
if errorlevel 1 (
  echo.
  echo Could not start. Is Rancher Desktop open and running? See docs\OFFLINE_INSTALL.md
  pause
  exit /b 1
)
echo.
echo TASEMS is starting. In one minute it opens at http://localhost:8000
echo Other computers in the office: http://THIS-COMPUTER-IP:8000  (IPv4 Address below)
ipconfig | findstr /i "IPv4"
timeout /t 60 >nul
start http://localhost:8000
pause
