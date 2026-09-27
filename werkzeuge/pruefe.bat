@echo off
rem Prueft den Stand vor einer Veroeffentlichung (Fassung 1, 27.09.2026).
rem Laeuft pruefe.py: beide Testsuiten, Lint, pyflakes, Deutsch-Scanner.
rem Am Ende steht in EINER Zeile, ob veroeffentlicht werden darf.
rem Bericht: berichte\pruefe_bericht.txt
cd /d "%~dp0.."
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"
echo Pruefung laeuft - das dauert einige Minuten ...
python pruefe.py
