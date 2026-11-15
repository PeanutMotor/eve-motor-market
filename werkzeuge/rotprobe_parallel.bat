@echo off
rem UTF-8 fuer Berichte (Konvention wie die anderen werkzeuge\*.bat).
rem Die .bat selbst bleibt rein ASCII.
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
rem ROTPROBE PARALLEL (emm823, Nutzer 02.11.2026: "Einen weg finden die
rem ganzen Rotproben zu beschleunigen"). Ersetzt die 16 Pakete
rem rotprobe_nacht_01..16.bat: ein Start faehrt ALLE Mutationen durch,
rem auf mehreren Kernen gleichzeitig, mit eigener Arbeitskopie je Lauf.
rem Gemessen (Container): ~40 h vorher, ~7 h bei 4 gleichzeitigen Laeufen.
rem
rem Standard ist die HALBE Kernzahl - der PC bleibt benutzbar (emm811).
rem Mehr Tempo, aber der PC wird zaeh: die naechste Zeile entkommentieren
rem und die Zahl setzen (hoechstens die Kernzahl).
rem set EMM_ROTPROBE_PROZESSE=4
rem
rem Nach einem Abbruch macht ein neuer Start dort weiter, wo jeder
rem Streifen stand. ALLES VON VORNE: diese Datei mit --neu starten, also
rem   python werkzeuge\rotprobe_parallel.py --neu
cd /d "%~dp0.."
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"
echo Rotprobe parallel laeuft - Fortschritt steht in
echo berichte\rotprobe_parallel.txt, Befunde in
echo berichte\rotprobe_parallel_BLIND.txt. Der PC bleibt an.
python werkzeuge\rotprobe_parallel.py %*
pause
