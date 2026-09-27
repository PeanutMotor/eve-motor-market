@echo off
rem Zeigt, wie der Gewinn auf jeder Karte in "Meine Bauplaene" entsteht
rem (Fassung 1, 26.09.2026). Schreibt berichte\karten_bericht.txt.
rem Liest nur, aendert nichts.
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    call .venv\Scripts\activate.bat
)
if not exist "berichte" mkdir "berichte"
set QT_QPA_PLATFORM=offscreen
python werkzeuge\zeige_karten.py
pause
