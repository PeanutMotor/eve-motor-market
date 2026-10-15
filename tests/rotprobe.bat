@echo off
rem UTF-8 fuer Berichte (emm511, Nutzer 10.10.2026: der Bericht
rem liess sich nicht hochladen - 'Fehlende Kodierung'). Windows-
rem Werkzeuge (robocopy, dir, git) schreiben sonst in der Konsolen-
rem Codepage. Die .bat selbst MUSS dafuer rein ASCII bleiben.
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
REM ============================================================
REM  EVE Trade Ledger - ROTPROBE KOMPLETTLAUF
REM
REM  Doppelklick genuegt. Der Lauf dreht JEDE der 242 Absicherungen
REM  einzeln zurueck und prueft, ob die zugehoerige Pruefung dabei
REM  auch wirklich rot wird. Dauer: mehrere Stunden - am besten
REM  abends starten und ueber Nacht laufen lassen.
REM
REM  Es wird NICHTS an deinen Daten oder am Programm geaendert:
REM  die Rotprobe arbeitet auf einer Kopie im Temp-Ordner.
REM
REM  Ergebnis landet in  berichte\rotprobe_komplett.txt.
REM  (Angelegt in Sitzung 10 fuer den Komplettlauf nach Auftrag E.)
REM ============================================================
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
    echo [Erststart] Richte Umgebung ein, das dauert einmalig 1-2 Minuten...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

echo.
echo ==========================================================
echo  Rotprobe laeuft. Das dauert MEHRERE STUNDEN.
echo  Dieses Fenster bitte offen lassen - der PC darf dabei
echo  nicht in den Ruhezustand gehen.
echo.
echo  Ergebnis:  berichte\rotprobe_komplett.txt
echo ==========================================================
echo.

if not exist "berichte" mkdir "berichte"
python tests\rotprobe.py > berichte\rotprobe_komplett.txt 2>&1

echo.
echo FERTIG. Die letzte Zeile in berichte\rotprobe_komplett.txt sagt,
echo wie viele der 242 Mutationen erkannt wurden.
echo Diese Datei bitte in den naechsten Chat haengen.
echo.
pause
