@echo off
setlocal
cd /d "%~dp0.."
set "SAKURA_BUILD_PYTHON=%CD%\venv\Scripts\python.exe"
if not exist "%SAKURA_BUILD_PYTHON%" (
  echo Build Python is missing. Restore Sakura's development venv first.
  if not exist "C:\AI\Installer ready" mkdir "C:\AI\Installer ready"
  >"C:\AI\Installer ready\Build-Errors.md" echo # Sakura EXE build errors
  >>"C:\AI\Installer ready\Build-Errors.md" echo The development venv is missing. Restore Sakura/venv before building.
  if not "%~1"=="--no-pause" pause
  exit /b 1
)
"%SAKURA_BUILD_PYTHON%" -u "tools\build-split-installers.py" --output "C:\AI\Installer ready"
set "SAKURA_BUILD_RESULT=%ERRORLEVEL%"
if "%SAKURA_BUILD_RESULT%"=="0" (
  echo.
  echo SUCCESS: Separate installers in C:\AI\Installer ready\Sakura VTuber and Sakura Companion
) else (
  echo.
  echo FAILED: Read C:\AI\Installer ready\split-build-reports\Errors.md
)
if not "%~1"=="--no-pause" pause
exit /b %SAKURA_BUILD_RESULT%
