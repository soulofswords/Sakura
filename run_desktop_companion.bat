@echo off
setlocal
title Sakura - Anime Desktop Companion (Transparent)
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"
set "SAKURA_DESKTOP=1"

echo ========================================================
echo   Sakura - Transparent Desktop Companion
echo ========================================================
echo.

echo Launching transparent floating desktop widget...
echo Drag the Sakura flower to move the window. Drag an edge to resize it.
echo.

if not exist "%~dp0venv\Scripts\python.exe" (
    echo [ERROR] Project Python environment not found.
    echo Run setup.bat to install dependencies, then try again.
    pause
    exit /b 1
)

REM Sakura starts and manages its bundled runtime; no system Ollama is needed.
"%~dp0venv\Scripts\python.exe" -u "%~dp0desktop.py"
set "SAKURA_EXIT=%ERRORLEVEL%"
if not "%SAKURA_EXIT%"=="0" (
    echo.
    echo [ERROR] Sakura stopped with exit code %SAKURA_EXIT%.
    echo The startup error is shown above.
    pause
)

exit /b %SAKURA_EXIT%
