@echo off
rem UTF-8 fuer Berichte (emm511, Nutzer 10.10.2026: der Bericht
rem liess sich nicht hochladen - 'Fehlende Kodierung'). Windows-
rem Werkzeuge (robocopy, dir, git) schreiben sonst in der Konsolen-
rem Codepage. Die .bat selbst MUSS dafuer rein ASCII bleiben.
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
rem Listet die Items OHNE Preishistorie und klaert, ob sie wirklich
rem nicht gehandelt werden oder ob der Abruf nur scheiterte
rem (Fassung 1, 11.11.2026). Schreibt berichte\historie_bericht.txt.
rem Liest die Datenbank und fragt zur Probe bis zu 60 Items bei ESI
rem nach - aendert sonst nichts.
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    call .venv\Scripts\activate.bat
)
if not exist "berichte" mkdir "berichte"
python werkzeuge\pruefe_historie.py
pause
