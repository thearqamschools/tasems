@echo off
rem Makes a master login (every permission in every branch). Run it after TASEMS has started.
cd /d "%~dp0.."
docker compose -f docker-compose.offline.yml exec web python manage.py createsuperuser
pause
