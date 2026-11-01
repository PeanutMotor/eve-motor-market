@echo off
rem UTF-8 fuer Berichte (emm511): Windows-Werkzeuge schreiben sonst in
rem der Konsolen-Codepage, dann laesst sich der Bericht nicht hochladen.
rem Die .bat selbst MUSS dafuer rein ASCII bleiben.
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
rem Zeigt, welche Blaupausen Eve MoMa von dir sieht und welche der
rem Blueprints-Reiter deshalb rot als fehlend meldet (Fassung 5).
rem Schreibt berichte\blaupausen_bericht.txt. Liest nur, aendert nichts.
rem SUCHWORT FUER ABSCHNITT 3b als Argument, mehrere mit Komma:
rem   zeige_blaupausen.bat Helium Fuel Block,Magnate,R.A.M.
rem Ohne Argument gilt die Vorgabe im Werkzeug.
if not "%~1"=="" set "BP_SUCHE=%*"
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    call .venv\Scripts\activate.bat
)
if not exist "berichte" mkdir "berichte"
python werkzeuge\zeige_blaupausen.py
pause
