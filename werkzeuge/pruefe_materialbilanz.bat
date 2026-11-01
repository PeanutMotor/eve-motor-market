@echo off
rem UTF-8 fuer Berichte (emm511) - die .bat selbst bleibt reines ASCII.
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
rem Sucht fehlendes Material: was hat ein Plan aus dem Bestand eingeplant,
rem das heute nicht mehr da ist - und wo ist es hin? Braucht ESI.
rem   python werkzeuge\pruefe_materialbilanz.py --plan Minmatar
rem   python werkzeuge\pruefe_materialbilanz.py --zeilen 40
rem Schreibt berichte\materialbilanz_bericht.txt. Aendert nichts.
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    call .venv\Scripts\activate.bat
)
if not exist "berichte" mkdir "berichte"
python werkzeuge\pruefe_materialbilanz.py %*
pause
