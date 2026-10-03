@echo off
rem Fassung 1 - Sicherung von Eve MoMa 1.1.0 nach Backup_MotorMarket\1.1.0
rem Nutzer 02.10.2026: "jetzt noch ein backup erstellen von 1.1.0" (vor dem
rem Release, Stand: alles gruen, Release-Texte fertig).
rem 1) Release-Texte 1.1.0 (+ EXE und Quelltext-Zip, falls schon gebaut)
rem 2) der Arbeitsordner (mit .git, CLAUDE.md, MEMORY.md, OFFENE_PUNKTE,
rem    .smoke_home) - ohne .venv/build/dist/__pycache__
rem 3) die Programmdaten aus %%APPDATA%%\EVE Motor Market (Plaene, Einstellungen)
rem 4) alles zusammen als EIN Zip: Backup_MotorMarket\EVE-MoMa-1.1.0-komplett.zip
rem    (tar.exe statt Compress-Archive: kommt mit ueber 2 GB zurecht)
cd /d "%~dp0.."
set "Z=%~dp0..\..\Backup_MotorMarket\1.1.0"
set "ZIP=%~dp0..\..\Backup_MotorMarket\EVE-MoMa-1.1.0-komplett.zip"
set "B=%~dp0..\berichte\sicherung_1.1.0_bericht.txt"
if not exist "%~dp0..\berichte" mkdir "%~dp0..\berichte"
echo Sicherung 1.1.0 - Fassung 1 > "%B%"
echo Start: %date% %time% >> "%B%"
if not exist "%Z%" mkdir "%Z%"
echo Sicherung laeuft ... das dauert einige Minuten.

echo --- 1) Release-Dateien --- >> "%B%"
for %%F in (RELEASE_1.1.0.txt PATCHNOTES_1.1.0_DISCORD.txt README_1.1.0.txt REDDIT_POST_1.1.0.txt) do copy /y "release\%%F" "%Z%\" >> "%B%" 2>&1
if exist "eve-motor-market-source-1.1.0.zip" (
  copy /y "eve-motor-market-source-1.1.0.zip" "%Z%\" >> "%B%" 2>&1
  copy /y "dist\EVE Motor Market.exe" "%Z%\EVE-Motor-Market-1.1.0.exe" >> "%B%" 2>&1
) else (
  echo HINWEIS: EXE und Quelltext-Zip 1.1.0 noch nicht gebaut - nach dem Release diese Datei erneut starten >> "%B%"
)

echo --- 2) Arbeitsordner --- >> "%B%"
robocopy . "%Z%\arbeitsordner_1.1.0" /E /XD .venv build dist __pycache__ /NFL /NDL /NP >> "%B%" 2>&1
if %errorlevel% GEQ 8 echo WARNUNG: robocopy Arbeitsordner meldet Fehler %errorlevel% >> "%B%"

echo --- 3) Programmdaten (APPDATA) --- >> "%B%"
robocopy "%APPDATA%\EVE Motor Market" "%Z%\programmdaten_appdata" /E /NFL /NDL /NP >> "%B%" 2>&1
if %errorlevel% GEQ 8 echo WARNUNG: robocopy Programmdaten meldet Fehler %errorlevel% >> "%B%"

echo --- 4) Zip --- >> "%B%"
if exist "%ZIP%" del "%ZIP%"
tar -a -c -f "%ZIP%" -C "%Z%" . >> "%B%" 2>&1
if errorlevel 1 echo WARNUNG: tar meldet einen Fehler >> "%B%"

echo --- Inhalt --- >> "%B%"
dir "%Z%" >> "%B%"
dir "%ZIP%" >> "%B%"
echo Ende: %date% %time% >> "%B%"
echo Fertig. Bericht: berichte\sicherung_1.1.0_bericht.txt
pause
