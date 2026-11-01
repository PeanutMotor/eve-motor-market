@echo off
rem UTF-8 fuer Berichte (emm511) - die .bat selbst bleibt reines ASCII.
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
rem Spielt viele Bauplan-Lagen durch und prueft die Zusagen des Bauplans.
rem Braucht KEIN ESI und keine Datenbank - laeuft ueberall.
rem   python werkzeuge\szenarien_bauplan.py --anzahl 500 --samen 7
rem   python werkzeuge\szenarien_bauplan.py --zeige 30
rem Schreibt berichte\szenarien_bericht.txt. Aendert nichts.
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    call .venv\Scripts\activate.bat
)
if not exist "berichte" mkdir "berichte"
python werkzeuge\szenarien_bauplan.py %*
pause
