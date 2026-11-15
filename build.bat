@echo off
REM ============================================================
REM  EVE Trade Ledger - build a standalone Windows .exe
REM  Run this on Windows after installing Python 3.10+.
REM ============================================================

echo [1/5] Creating virtual environment...
python -m venv .venv
call .venv\Scripts\activate.bat

echo [2/5] Installing dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller

echo [3/5] Building icon...
REM  ERZEUGT, NICHT GEPFLEGT: das Logo wird in eve_trader/ui/icons.py
REM  gezeichnet. Eine daneben abgelegte .ico waere eine zweite Wahrheit -
REM  aendert jemand das Logo im Code, zeigte die EXE weiter das alte Bild.
REM  Deshalb hier bei JEDEM Bau neu aus dem Code erzeugen.
python mache_icon.py
if errorlevel 1 (
  echo    Icon konnte nicht erzeugt werden - Bau wird abgebrochen.
  echo    Ohne Icon haette die EXE das nichtssagende Standardsymbol.
  pause
  exit /b 1
)

echo [4/5] Building EXE...
REM  --add-data: DATENDATEIEN muss PyInstaller ausdruecklich mitnehmen.
REM  Es packt von sich aus nur importierte Python-Module - die SVGs fuer die
REM  Checkbox-Haken und die Spinner-Pfeile kommen NUR ueber diese Zeile mit.
REM  Ohne sie sieht man in der fertigen EXE leere Kaestchen und leere
REM  Pfeilflaechen, waehrend beim Entwickeln alles stimmt.
REM  --icon setzt das Symbol der EXE-DATEI (Explorer, Taskleiste, Verknuepfung).
REM  Das FENSTER-Symbol kommt getrennt davon aus dem Code (icons.logo_icon).
REM  ACHTUNG - bei --add-data darf AUSSCHLIESSLICH der assets-Ordner stehen.
REM  Wer hier einen Projektordner mitgibt, packt settings.json (mit client_id
REM  und Charakter-IDs), ledger.db (Handelsdaten) und .smoke_home in JEDE
REM  ausgelieferte EXE. Die Pruefung "aa222" in test_bestand_herkunft.py
REM  schlaegt an, wenn das passiert - Aenderungen hier also erst dort
REM  gegenlesen.
REM  --onedir STATT --onefile (emm866, Nutzer: "der generelle
REM  erststart von Moma dauert lange"): eine onefile-EXE entpackt
REM  bei JEDEM Start ~200 MB nach %TEMP% (und der Virenscanner
REM  liest alles mit) - das sind viele Sekunden, bevor ueberhaupt
REM  Python laeuft. onedir startet direkt aus dem Programmordner;
REM  der Installer packt den Ordner dist\EVE Motor Market ein.
pyinstaller --noconfirm --onedir --windowed ^
  --name "EVE Motor Market" ^
  --icon "eve_trader/ui/assets/logo.ico" ^
  --add-data "eve_trader/ui/assets;eve_trader/ui/assets" ^
  --hidden-import keyring.backends.Windows ^
  --collect-submodules pyqtgraph ^
  main.py

echo.
echo [5/5] Building installer (optional)...
REM  NAME UND VERSION AUS EINER QUELLE: beide stehen in
REM  eve_trader/__init__.py und werden hier ausgelesen, statt sie in der
REM  .iss ein zweites Mal einzutippen. Sonst laeuft die Version im
REM  Installer irgendwann der Version im Programm hinterher, und die
REM  Update-Pruefung meldet Unsinn.
for /f "delims=" %%v in ('python -c "import eve_trader;print(eve_trader.__version__)"') do set MM_VER=%%v
for /f "delims=" %%n in ('python -c "import eve_trader;print(eve_trader.APP_NAME)"') do set MM_NAME=%%n

REM  Inno Setup ist NICHT Pflicht. Wer nur die EXE weitergeben will,
REM  braucht es nicht - der Bau darf daran also nicht scheitern.
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
REM  Ohne Adminrechte installiert (winget, "nur fuer mich") liegt Inno
REM  Setup unter %LOCALAPPDATA%\Programs - emm944: dort stand es bei
REM  ihm, und der Installer wurde still uebersprungen.
if not exist "%ISCC%" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
  echo    Inno Setup 6 nicht gefunden - Installer uebersprungen.
  echo    Die fertige EXE liegt trotzdem in dist\ und laeuft eigenstaendig.
  echo    Inno Setup gibt es kostenlos: https://jrsoftware.org/isdl.php
  goto :fertig
)
"%ISCC%" /DMyAppName="%MM_NAME%" /DMyAppVersion="%MM_VER%" installer.iss
echo    Installer: dist\EVE-Motor-Market-%MM_VER%-setup.exe

:fertig
echo.
echo Done. Your program is in:  dist\EVE Motor Market\EVE Motor Market.exe
pause
