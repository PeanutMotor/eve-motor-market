@echo off
rem Prueft die FRACHT der Verkaufsliste an deinen echten Kaeufen
rem (Fassung 1, 29.09.2026). Rechnet sie zweimal (Programm + unabhaengige
rem Zweitrechnung) und vergleicht. Schreibt berichte\fracht_bericht.txt.
rem Liest nur, aendert nichts, kein Internet noetig.
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    call .venv\Scripts\activate.bat
)
if not exist "berichte" mkdir "berichte"
python werkzeuge\pruefe_fracht.py
pause
