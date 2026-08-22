@echo off
cd /d "%~dp0\..\.."
py -3 scripts\start_app.py
if errorlevel 1 pause
