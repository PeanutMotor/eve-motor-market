@echo off
rem UTF-8 fuer Berichte (emm511) - die .bat selbst bleibt reines ASCII.
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
rem Stellt den Reservierungs-Fehler aus emm638 NACH und rechnet beide Wege
rem durch: alt (nur plan-eigener Stempel) gegen neu (juengster Abruf).
rem Vorgabe: jeder Haken 2400 s nach dem Einfrieren. Eigene Werte:
rem   python werkzeuge\simuliere_reservierung.py --verzug 7200
rem   python werkzeuge\simuliere_reservierung.py --echt
rem   python werkzeuge\simuliere_reservierung.py --plan Minmatar
rem Schreibt berichte\reservierung_simulation_bericht.txt. Aendert nichts.
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    call .venv\Scripts\activate.bat
)
if not exist "berichte" mkdir "berichte"
python werkzeuge\simuliere_reservierung.py %*
pause
