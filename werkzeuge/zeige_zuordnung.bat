@echo off
rem UTF-8 fuer Berichte (emm511, Nutzer 10.10.2026: der Bericht
rem liess sich nicht hochladen - 'Fehlende Kodierung'). Windows-
rem Werkzeuge (robocopy, dir, git) schreiben sonst in der Konsolen-
rem Codepage. Die .bat selbst MUSS dafuer rein ASCII bleiben.
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
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
