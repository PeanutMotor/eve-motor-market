@echo off
rem Holt die Planer-Diagnose des Werkzeugs (Fassung 1, 26.09.2026) nach
rem berichte\planer_diagnose.txt. Die Datei schreibt das Programm bei JEDEM
rem Aufbau des Runplaners (Bauplan oeffnen) - also erst den Bauplan oeffnen,
rem dann diese Datei doppelklicken. Liest nur, aendert nichts.
cd /d "%~dp0.."
if not exist "berichte" mkdir "berichte"
set QUELLE=%APPDATA%\EVE Motor Market\planer_diagnose.txt
if not exist "%QUELLE%" set QUELLE=%APPDATA%\EveTradeLedger\planer_diagnose.txt
if not exist "%QUELLE%" (
    echo Keine planer_diagnose.txt gefunden - zuerst einen Bauplan oeffnen.
    pause
    exit /b 1
)
copy /y "%QUELLE%" "berichte\planer_diagnose.txt" >nul
echo Fassung 1 - kopiert nach berichte\planer_diagnose.txt
echo Quelle: %QUELLE%
pause
