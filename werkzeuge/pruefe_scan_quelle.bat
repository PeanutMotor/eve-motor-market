@echo off
rem UTF-8 fuer die Ausgabe - die .bat selbst bleibt reines ASCII.
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
rem Zeigt, von welchem Hub die gespeicherten Preise stammen. Nur lesend.
rem ALLES wird umgeleitet, auch Fehler (2>&1): bricht das Skript beim
rem Start ab, steht der Grund in der Datei statt in einem Fenster, das
rem sich gleich wieder schliesst.
cd /d "%~dp0.."
if not exist "berichte" mkdir "berichte"
if exist ".venv\Scripts\python.exe" (
    call .venv\Scripts\activate.bat
)
python werkzeuge\pruefe_scan_quelle.py %* > "berichte\scan_quelle.txt" 2>&1
type "berichte\scan_quelle.txt"
echo.
echo Geschrieben nach berichte\scan_quelle.txt
pause
