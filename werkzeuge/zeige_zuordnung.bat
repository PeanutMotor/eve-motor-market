@echo off
rem Zeigt, warum ein Material im eingefrorenen Bauplan ploetzlich fehlt,
rem und wem das Tool welchen Industrie-Job zuordnet (Fassung 1, 25.09.2026).
rem Schreibt berichte\zuordnung_bericht.txt. Liest nur, aendert nichts.
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    call .venv\Scripts\activate.bat
)
if not exist "berichte" mkdir "berichte"
python werkzeuge\zeige_zuordnung.py
pause
