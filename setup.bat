@echo off
title Sakura - Setup
cd /d "%~dp0"

echo ============================================
echo   Sakura - Anime AI Assistant Setup
echo ============================================
echo.

echo [1/3] Creating virtual environment...
python -m venv venv
call venv\Scripts\activate.bat

echo [2/3] Installing dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt

echo [3/3] Checking Ollama...
ollama list 2>nul
if %errorlevel% neq 0 (
    echo.
    echo WARNING: Ollama not found! Install from https://ollama.com
) else (
    echo Ollama OK!
    echo Pulling llama3.1:8b if not already downloaded...
    ollama pull llama3.1:8b
)

echo.
echo ============================================
echo   Setup complete!
echo   Double-click run_gui.bat to start!
echo ============================================
pause
