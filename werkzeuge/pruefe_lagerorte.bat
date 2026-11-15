@echo off
rem UTF-8 fuer Berichte (emm511). Die .bat selbst MUSS rein ASCII bleiben.
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
rem Zeigt, WOHER jeder Ort in "Stock locations" kommt - Hangar, Corp
rem oder offener Vertrag (Fassung 1, 13.11.2026, emm906). Schreibt
rem berichte\lagerorte_quelle.txt. Liest nur, aendert nichts.
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    call .venv\Scripts\activate.bat
)
if not exist "berichte" mkdir "berichte"
python werkzeuge\pruefe_lagerorte.py
pause
