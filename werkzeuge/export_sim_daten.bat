@echo off
rem UTF-8 fuer Berichte - die .bat selbst bleibt reines ASCII.
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
rem Holt Preise, Skills, Strukturen und die gespeicherten Plaene in EINE
rem Datei, damit sich jede Bauplan-Frage woanders nachrechnen laesst.
rem Keine Token, keine Charakternamen, kein Handelsjournal darin.
rem   python werkzeuge\export_sim_daten.py --esi --plan "Confessor"
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    call .venv\Scripts\activate.bat
)
if not exist "berichte" mkdir "berichte"
python werkzeuge\export_sim_daten.py --esi %*
pause
