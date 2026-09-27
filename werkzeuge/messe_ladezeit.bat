@echo off
rem Misst die Ladezeiten (Fassung 2, 27.09.2026: auch die Startzeit).
rem Startet EVE MoMa mit eingeschalteter Messung. Dann den langsamen
rem Bauplan / Multi-Bauplan oeffnen, warten bis er fertig geladen ist,
rem EVE MoMa schliessen. Der Bericht steht in berichte\ladezeiten.txt.
rem Ohne diese Datei gestartet misst das Programm NICHTS.
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    call .venv\Scripts\activate.bat
)
if not exist "berichte" mkdir "berichte"
if exist "berichte\ladezeiten.txt" del "berichte\ladezeiten.txt"
set EMM_LADEZEIT=1
echo Messung laeuft. Die Startzeit wird immer gemessen.
echo Optional einen langsamen Bauplan oeffnen, fertig laden lassen,
echo dann EVE MoMa schliessen.
python main.py
set EMM_LADEZEIT=
echo.
if exist "berichte\ladezeiten.txt" (
    echo Bericht: berichte\ladezeiten.txt
) else (
    echo Kein Bericht entstanden.
)
pause
