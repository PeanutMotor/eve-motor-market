@echo off
rem UTF-8 fuer Berichte (emm511, Nutzer 10.10.2026: der Bericht
rem liess sich nicht hochladen - 'Fehlende Kodierung'). Windows-
rem Werkzeuge (robocopy, dir, git) schreiben sonst in der Konsolen-
rem Codepage. Die .bat selbst MUSS dafuer rein ASCII bleiben.
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
rem Zeigt deine OFFENEN MARKET-ORDERS so, wie das Tool sie von ESI
rem bekommt (Fassung 1, 22.09.2026) - fuer den Befund "Portfolio zeigt
rem Buy Orders, die es im Spiel nicht gibt".
rem Schreibt berichte\orders_bericht.txt. Liest nur, aendert nichts -
rem weder deine Datenbank noch deine Orders im Spiel.
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    call .venv\Scripts\activate.bat
)
if not exist "berichte" mkdir "berichte"
python werkzeuge\zeige_orders.py
pause
