@echo off
rem UTF-8 fuer Berichte (emm511, Nutzer 10.10.2026: der Bericht
rem liess sich nicht hochladen - 'Fehlende Kodierung'). Windows-
rem Werkzeuge (robocopy, dir, git) schreiben sonst in der Konsolen-
rem Codepage. Die .bat selbst MUSS dafuer rein ASCII bleiben.
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
rem Diagnose fuer den Gewinne-Tab (Fassung 1, 04.10.2026): aelteste Daten,
rem Umsatz je Monat, Verkaeufe ohne Kauf-Lot (fallen aus der Anzeige).
rem Schreibt berichte\gewinn_verlauf_bericht.txt. Liest nur, aendert nichts.
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    call .venv\Scripts\activate.bat
)
if not exist "berichte" mkdir "berichte"
python werkzeuge\zeige_gewinn_verlauf.py
pause
