@echo off
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
