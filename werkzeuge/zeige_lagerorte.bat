@echo off
rem Zeigt, warum "Stock locations" ein Material als fehlend meldet:
rem Bedarf, Bestand, Jobs ohne Plan und abgeschlossene Plaene
rem (Fassung 2, 08.10.2026).
rem Schreibt berichte\lagerorte_bericht.txt. Liest nur, aendert nichts.
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    call .venv\Scripts\activate.bat
)
if not exist "berichte" mkdir "berichte"
python werkzeuge\zeige_lagerorte.py
pause
