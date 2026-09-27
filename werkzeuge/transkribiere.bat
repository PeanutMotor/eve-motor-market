@echo off
REM Sprache -> Text (Deutsch) fuer YouTube-Tutorials. Doppelklick -> Datei
REM waehlen (oder Datei auf die .bat ziehen). Ergebnis liegt NEBEN dem Video:
REM   <video>.de.txt  (Text mit Zeitmarken)   <video>.de.srt  (Untertitel)
REM Fassung 3 (19.09.2026, Dateiauswahl; Liste ohne BOM - Fassung 2 gab Python
REM einen Pfad mit unsichtbarem Zeichen davor, "FEHLT"). Erster Lauf: installiert
REM faster-whisper und laedt das Modell (~1,5 GB) - dauert einige Minuten.
REM Bericht: berichte\transkript_bericht.txt
setlocal enabledelayedexpansion
cd /d "%~dp0.."
if not exist "berichte" mkdir "berichte"
set B=berichte\transkript_bericht.txt
set LISTE=berichte\transkript_dateien.txt
echo Fassung 3 - %DATE% %TIME% > "%B%"
if exist "%LISTE%" del "%LISTE%"
if "%~1"=="" goto auswahl
:args
if "%~1"=="" goto weiter
>>"%LISTE%" echo %~1
shift
goto args
:auswahl
echo Dateiauswahl ... >> "%B%"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Add-Type -AssemblyName System.Windows.Forms;" ^
  "$d = New-Object System.Windows.Forms.OpenFileDialog;" ^
  "$d.Title = 'Video oder Audio waehlen (MoMa Transkription)';" ^
  "$d.Filter = 'Video/Audio|*.mp4;*.mkv;*.webm;*.mov;*.mp3;*.m4a;*.wav;*.ogg|Alle|*.*';" ^
  "$d.Multiselect = $true;" ^
  "if ($d.ShowDialog() -eq 'OK') { $d.FileNames | Out-File -Encoding Default '%LISTE%' }"
:weiter
if not exist "%LISTE%" (
  echo Keine Datei gewaehlt. >> "%B%"
  type "%B%"
  pause
  exit /b 1
)
if exist ".venv\Scripts\python.exe" (set PY=.venv\Scripts\python.exe) else (set PY=python)
%PY% -c "import faster_whisper" >nul 2>&1 || (
  echo faster-whisper wird installiert ... >> "%B%"
  echo faster-whisper wird installiert - einmalig, bitte warten ...
  %PY% -m pip install faster-whisper >> "%B%" 2>&1
)
for /f "usebackq delims=" %%F in ("%LISTE%") do (
  echo -- %%F >> "%B%"
  echo.
  echo === %%F
  %PY% werkzeuge\transkribiere.py "%%F"
  if errorlevel 1 (echo FEHLER bei %%F >> "%B%") else (echo fertig: %%~dpnF.de.txt >> "%B%")
)
echo.
echo Fertig - Texte liegen NEBEN den Videos ^(.de.txt / .de.srt^). Bericht in %B%
type "%B%"
pause
