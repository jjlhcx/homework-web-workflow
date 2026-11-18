@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0cx.ps1" open
if errorlevel 1 pause
