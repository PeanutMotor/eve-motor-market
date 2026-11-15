@echo off
rem UTF-8 fuer Berichte - die .bat selbst bleibt reines ASCII.
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
rem Rechnet einen Bauplan aus berichte\sim_daten.json nach - ohne Fenster.
rem   python werkzeuge\sim_plan.py --item 34317 --kurve 1,2,4,8,12
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    call .venv\Scripts\activate.bat
)
python werkzeuge\sim_plan.py %*
pause
