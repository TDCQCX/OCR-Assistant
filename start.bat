@echo off
rem Launch GUI app in background (no console), close this cmd window.
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" "main.py"
exit
