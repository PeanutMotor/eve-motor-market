@echo off
rem Szenario Bau-Prioritaet (Fassung 1, 28.09.2026): spielt Umsortieren mitten
rem im Bauen durch - mit den echten Funktionen, eigene Temp-Datenbank.
rem Liest und aendert nichts an deinen Daten. Bericht: berichte\szenario_bericht.txt
cd /d "%~dp0.."
if not exist "berichte" mkdir "berichte"
set PY=python
if exist ".venv\Scripts\python.exe" set PY=.venv\Scripts\python.exe
echo Fassung 1 > "berichte\szenario_bericht.txt"
%PY% werkzeuge\szenario_prioritaet.py >> "berichte\szenario_bericht.txt" 2>&1
type "berichte\szenario_bericht.txt"
pause
