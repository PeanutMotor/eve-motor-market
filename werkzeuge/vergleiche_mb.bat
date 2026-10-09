@echo off
rem Vergleicht My Blueprints mit dem Bauplan (Fassung 2, 06.10.2026, emm437).
rem Startet EVE MoMa mit eingeschaltetem Vergleich. Dann:
rem   1. Industry - My Blueprints - "Load blueprints" (warten bis fertig)
rem   2. die Zeile als Bauplan oeffnen, warten bis er fertig gerechnet hat
rem      (WARTEN bis unten "Bericht geschrieben" steht - bei grossen
rem      Plaenen kann das eine Minute dauern)
rem   3. EVE MoMa schliessen
rem Der Bericht steht in berichte\mb_vergleich_bericht.txt.
rem Ohne diese Datei gestartet vergleicht das Programm NICHTS.
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    call .venv\Scripts\activate.bat
)
if not exist "berichte" mkdir "berichte"
if exist "berichte\mb_vergleich_bericht.txt" del "berichte\mb_vergleich_bericht.txt"
set EMM_MB_VERGLEICH=1
echo Vergleich laeuft.
echo 1. My Blueprints laden  2. Zeile als Bauplan oeffnen
echo 3. WARTEN bis unten "Bericht geschrieben" steht  4. EVE MoMa schliessen
python main.py
set EMM_MB_VERGLEICH=
echo.
if exist "berichte\mb_vergleich_bericht.txt" (
    echo Bericht: berichte\mb_vergleich_bericht.txt
    start "" notepad "berichte\mb_vergleich_bericht.txt"
) else (
    echo Kein Bericht entstanden - My Blueprints vorher geladen?
)
pause
