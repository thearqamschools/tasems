@echo off
rem DELETES ALL TASEMS DATA on this computer (students, fees, logins). Only for starting the test again.
cd /d "%~dp0.."
set /p ANSWER=Type DELETE to remove all TASEMS data on this computer: 
if not "%ANSWER%"=="DELETE" (
  echo Nothing deleted.
  pause
  exit /b 0
)
docker compose -f docker-compose.offline.yml down -v
echo All data removed. Start again with START-TASEMS.bat or START-EMPTY-REAL-TEST.bat
pause
