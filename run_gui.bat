@echo off
setlocal
title Sakura - Anime AI Assistant (3D GUI)
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"
set "SAKURA_DESKTOP=0"

echo ========================================================
echo   Sakura - Anime AI Assistant (3D GUI App)
echo ========================================================
echo.

echo Starting Sakura on an available localhost port ...
echo Opening your default browser...
echo.

if not exist "%~dp0venv\Scripts\python.exe" (
    echo [ERROR] Project Python environment not found.
    echo Run setup.bat to install dependencies, then try again.
    pause
    exit /b 1
)

REM The backend owns its configured local model server and its cleanup.
REM Launch directly with the project interpreter; activation is unnecessary.
"%~dp0venv\Scripts\python.exe" -u "%~dp0app.py"
set "SAKURA_EXIT=%ERRORLEVEL%"
if not "%SAKURA_EXIT%"=="0" (
    echo.
    echo [ERROR] Sakura stopped with exit code %SAKURA_EXIT%.
    echo The startup error is shown above. Keep this window open to read it.
    pause
)

exit /b %SAKURA_EXIT%
