@echo off
rem UTF-8 fuer Berichte (Konvention wie die anderen werkzeuge\*.bat).
rem Die .bat selbst bleibt rein ASCII - das haelt rotprobe_ueber_nacht.py
rem genauso ein.
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
rem Rotprobe UEBER NACHT, Paket 08 von 16 (emm551, Nutzer
rem 14.10.2026: die volle Rotprobe in 2-Stunden-Pakete gepackt, danach
rem faehrt der PC automatisch runter - mehrere Naechte hintereinander).
rem Die Nummer ist nur ein Merkzettel, welche Nacht das ist - der
rem Fortschritt steht in berichte\rotprobe_fortschritt.txt und macht
rem IMMER da weiter, wo die letzte Nacht aufgehoert hat. Ist alles schon
rem durchgelaufen, tut dieses Paket nichts mehr und der PC bleibt an.
cd /d "%~dp0.."
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"
set EMM_ROTPROBE_BUDGET_S=7200
echo Rotprobe Paket 08 von 16 laeuft - das dauert bis zu 2 Stunden ...
echo Ergebnis steht in berichte\rotprobe_nacht.txt (Befunde zusaetzlich in
echo berichte\rotprobe_nacht_BLIND.txt). Der PC faehrt danach herunter.
python werkzeuge\rotprobe_ueber_nacht.py
