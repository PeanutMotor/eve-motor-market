@echo off
rem UTF-8 fuer Berichte (emm511, Nutzer 10.10.2026: der Bericht
rem liess sich nicht hochladen - 'Fehlende Kodierung'). Windows-
rem Werkzeuge (robocopy, dir, git) schreiben sonst in der Konsolen-
rem Codepage. Die .bat selbst MUSS dafuer rein ASCII bleiben.
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
rem Prueft den Stand vor einer Veroeffentlichung (Fassung 1, 27.09.2026).
rem Laeuft pruefe.py: beide Testsuiten, Lint, pyflakes, Deutsch-Scanner.
rem Am Ende steht in EINER Zeile, ob veroeffentlicht werden darf.
rem Bericht: berichte\pruefe_bericht.txt
cd /d "%~dp0.."
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"
echo Pruefung laeuft - das dauert einige Minuten ...
python pruefe.py
