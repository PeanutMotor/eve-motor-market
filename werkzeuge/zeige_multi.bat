@echo off
rem Zeigt, wie deine MULTI-BAUPLAENE rechnen (Fassung 1, 20.09.2026).
rem Schreibt berichte\multi_bericht.txt. Vorher einmal "Load recipes"
rem im Tool druecken und mindestens einen Multi-Bauplan gespeichert haben.
rem Liest nur - es wird nichts veraendert.
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    call .venv\Scripts\activate.bat
)
if not exist "berichte" mkdir "berichte"
python werkzeuge\zeige_multi.py
pause
