@echo off
rem UTF-8 fuer Berichte (emm511) - die .bat selbst bleibt reines ASCII.
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
rem Stellt einen Bestandsverlust NACH und rechnet beide Wege durch:
rem alt (max(Einfrier-Bestand, live)) gegen neu (echter Stand).
rem Vorgabe: 30 Prozent Verlust. Eigene Werte:
rem   python werkzeuge\simuliere_bestandsverlust.py --verlust 50
rem   python werkzeuge\simuliere_bestandsverlust.py --item Tungsten --weg 5000
rem Schreibt berichte\verlust_simulation_bericht.txt. Aendert nichts.
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    call .venv\Scripts\activate.bat
)
if not exist "berichte" mkdir "berichte"
python werkzeuge\simuliere_bestandsverlust.py %*
pause
