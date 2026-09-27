@echo off
rem SICHERUNG (Fassung 1, 26.09.2026): kopiert den Quelltext UND deine Daten
rem (Einstellungen, Bauplaene, Datenbank aus %APPDATA%) in einen Ordner mit
rem Datum und Uhrzeit. Es wird NUR KOPIERT, nichts veraendert oder geloescht.
rem
rem ZURUECKSPIELEN: den gewuenschten Ordner unter _archiv\_sicherung_* oeffnen,
rem   - "projekt"  ueber den Projektordner kopieren (Dateien ersetzen),
rem   - "daten"    ueber %APPDATA%\EVE Motor Market kopieren (Programm vorher
rem                 schliessen).
cd /d "%~dp0.."
set STAMP=%date:~-4%-%date:~-7,2%-%date:~-10,2%_%time:~0,2%-%time:~3,2%
set STAMP=%STAMP: =0%
set ZIEL=_archiv\_sicherung_%STAMP%
if not exist "berichte" mkdir "berichte"
set BERICHT=berichte\sicherung_bericht.txt
echo Sicherung Fassung 1 - %STAMP% > "%BERICHT%"
echo Ziel: %ZIEL% >> "%BERICHT%"

echo == Quelltext ==>> "%BERICHT%"
robocopy "%CD%" "%ZIEL%\projekt" /E /XD _archiv .venv __pycache__ .git dist build berichte /XF *.pyc /NFL /NDL /NJH /NP >> "%BERICHT%"
if errorlevel 8 (echo FEHLER beim Kopieren des Quelltexts >> "%BERICHT%")

set DATEN=%APPDATA%\EVE Motor Market
if not exist "%DATEN%" set DATEN=%APPDATA%\EveTradeLedger
echo == Daten aus %DATEN% ==>> "%BERICHT%"
if exist "%DATEN%" (
    robocopy "%DATEN%" "%ZIEL%\daten" /E /NFL /NDL /NJH /NP >> "%BERICHT%"
    if errorlevel 8 (echo FEHLER beim Kopieren der Daten >> "%BERICHT%")
) else (
    echo Kein Datenordner gefunden. >> "%BERICHT%"
)
echo. >> "%BERICHT%"
echo FERTIG. Sicherung liegt in %ZIEL% >> "%BERICHT%"
type "%BERICHT%"
echo.
echo Sicherung liegt in: %ZIEL%
pause
