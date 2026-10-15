@echo off
rem UTF-8 fuer Berichte (emm511, Nutzer 10.10.2026: der Bericht
rem liess sich nicht hochladen - 'Fehlende Kodierung'). Windows-
rem Werkzeuge (robocopy, dir, git) schreiben sonst in der Konsolen-
rem Codepage. Die .bat selbst MUSS dafuer rein ASCII bleiben.
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
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
