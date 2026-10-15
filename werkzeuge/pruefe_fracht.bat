@echo off
rem UTF-8 fuer Berichte (emm511, Nutzer 10.10.2026: der Bericht
rem liess sich nicht hochladen - 'Fehlende Kodierung'). Windows-
rem Werkzeuge (robocopy, dir, git) schreiben sonst in der Konsolen-
rem Codepage. Die .bat selbst MUSS dafuer rein ASCII bleiben.
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
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
