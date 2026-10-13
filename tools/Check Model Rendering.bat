@echo off
setlocal
cd /d "%~dp0.."
set "SAKURA_CHECK_PYTHON=%CD%\venv\Scripts\python.exe"
if not exist "%SAKURA_CHECK_PYTHON%" (
  if not exist "C:\AI" mkdir "C:\AI"
  >"C:\AI\Model-Rendering-Errors.md" echo # Model rendering check errors
  >>"C:\AI\Model-Rendering-Errors.md" echo The project's development Python venv is missing.
  if not "%SAKURA_CHECK_NO_PAUSE%"=="1" pause
  exit /b 1
)
"%SAKURA_CHECK_PYTHON%" -u "tools\check-model-rendering.py" %*
set "SAKURA_CHECK_RESULT=%ERRORLEVEL%"
echo.
echo Results: C:\AI\Model-Rendering-Report.md
echo Issues: C:\AI\Model-Rendering-Errors.md
if not "%SAKURA_CHECK_NO_PAUSE%"=="1" pause
exit /b %SAKURA_CHECK_RESULT%
