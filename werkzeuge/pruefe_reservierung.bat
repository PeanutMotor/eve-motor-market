@echo off
rem UTF-8 fuer Berichte (emm511) - die .bat selbst bleibt reines ASCII.
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
rem Haelt ein Bauplan Material fest, das er gar nicht mehr verbraucht?
rem Stellt je Plan und Material Anspruch gegen den Verbrauch der noch
rem OFFENEN Runs und nennt die Verbraucher. Am Schluss: alle Ansprueche
rem gegen den echten Bestand.
rem Schreibt berichte\reservierung_bericht.txt. Liest nur, aendert nichts.
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    call .venv\Scripts\activate.bat
)
if not exist "berichte" mkdir "berichte"
python werkzeuge\pruefe_reservierung.py
pause
