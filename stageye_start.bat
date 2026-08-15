@echo off
cd /d "%~dp0"
taskkill /f /im pythonw.exe >nul 2>&1
start "" pyw -3.12 stageye_host.py
