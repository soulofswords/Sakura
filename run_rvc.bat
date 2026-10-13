@echo off
cd /d "%~dp0"
"%~dp0rvc-gpu-runtime\Scripts\python.exe" -u rvc_service.py
pause
