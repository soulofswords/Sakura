@echo off
setlocal
cd /d "%~dp0.."
if not defined NODE_PATH set "NODE_PATH=%LOCALAPPDATA%\..\..\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules"
if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules\playwright" set "NODE_PATH=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules"
venv\Scripts\python.exe tools\sync-jio-library.py --all-accounts
if errorlevel 1 (
  echo Library sync stopped. Existing models were kept. Review the message above.
) else (
  echo Library sync completed. Choose Refresh library in Sakura.
)
pause
