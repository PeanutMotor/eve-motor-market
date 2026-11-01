@echo off
rem UTF-8 fuer Berichte (emm511) - die .bat selbst bleibt reines ASCII.
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
rem Holt EINMAL alle Daten, die eine Ferndiagnose braucht: Hangar (Char und
rem Corp), laufende Jobs, Job-Zuordnung, Kaeufe, Namen. Nur lesend.
rem   python werkzeuge\exportiere_diagnose.py --seit 2026-09-01
rem Schreibt berichte\diagnose_export.json.
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    call .venv\Scripts\activate.bat
)
if not exist "berichte" mkdir "berichte"
python werkzeuge\exportiere_diagnose.py %*
pause
