@echo off
rem UTF-8 fuer Berichte (emm511) - die .bat selbst bleibt reines ASCII.
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
rem Warum fehlt ingame Material, obwohl der Bauplan sagt es sei da?
rem Vergleicht je Material: was der eingefrorene Plan rechnet gegen das,
rem was ESI wirklich sieht; prueft Ueberbuchung ueber alle aktiven Plaene,
rem zeigt die Verteilung je Ort/Charakter und die Reservierungen.
rem Schreibt berichte\bestand_luecke_bericht.txt. Liest nur, aendert nichts.
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    call .venv\Scripts\activate.bat
)
if not exist "berichte" mkdir "berichte"
python werkzeuge\pruefe_bestand_luecke.py %*
pause
