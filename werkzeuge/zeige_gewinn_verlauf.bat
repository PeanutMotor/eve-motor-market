@echo off
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
