@echo off
setlocal
cd /d "%~dp0.."
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"
set "SAKURA_RELEASE_OUTPUT=C:\AI\Installer ready"
set "SAKURA_RELEASE_REPORTS=%SAKURA_RELEASE_OUTPUT%\split-build-reports"
if not exist "%SAKURA_RELEASE_REPORTS%" mkdir "%SAKURA_RELEASE_REPORTS%"
set "SAKURA_BUILD_PYTHON=%CD%\venv\Scripts\python.exe"
if not exist "%SAKURA_BUILD_PYTHON%" (
  echo Build Python is missing. Restore Sakura's development venv first.
  if not exist "C:\AI\Installer ready" mkdir "C:\AI\Installer ready"
  >"C:\AI\Installer ready\Build-Errors.md" echo # Sakura EXE build errors
  >>"C:\AI\Installer ready\Build-Errors.md" echo The development venv is missing. Restore Sakura/venv before building.
  if not "%~1"=="--no-pause" pause
  exit /b 1
)
for /f %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "SAKURA_BUILD_STAMP=%%T"
set "SAKURA_BUILD_LOG=%SAKURA_RELEASE_REPORTS%\Build-%SAKURA_BUILD_STAMP%.log"
echo Building updated protected Companion and VTuber installers. Please wait.
echo Character models and personal data are excluded.
echo Solid compression keeps all runtime features; packing and unpacking may take longer.
echo Build log: %SAKURA_BUILD_LOG%
echo Protected macOS DMGs require a Mac build host; existing DMGs will remain unchanged.
"%SAKURA_BUILD_PYTHON%" -u "tools\build-split-installers.py" --output "%SAKURA_RELEASE_OUTPUT%" >"%SAKURA_BUILD_LOG%" 2>&1
set "SAKURA_BUILD_RESULT=%ERRORLEVEL%"
if not "%SAKURA_BUILD_RESULT%"=="0" goto build_failed
echo Installers passed verification. Refreshing the two local EXE launchers.
"%SAKURA_BUILD_PYTHON%" -u "tools\create-local-products.py" >>"%SAKURA_BUILD_LOG%" 2>&1
set "SAKURA_BUILD_RESULT=%ERRORLEVEL%"
if not "%SAKURA_BUILD_RESULT%"=="0" goto build_failed
copy /y "%SAKURA_BUILD_LOG%" "%SAKURA_RELEASE_REPORTS%\Build-latest.log" >nul
>"%SAKURA_RELEASE_OUTPUT%\Build-Errors.md" echo # Sakura rebuild status
>>"%SAKURA_RELEASE_OUTPUT%\Build-Errors.md" echo Latest rebuild passed. No errors. Log: %SAKURA_BUILD_LOG%
echo.
echo SUCCESS: Installers in %SAKURA_RELEASE_OUTPUT%\Sakura VTuber and Sakura Companion
echo Local EXEs refreshed in the parent project folder. Settings and artwork preserved.
goto finish
:build_failed
copy /y "%SAKURA_BUILD_LOG%" "%SAKURA_RELEASE_REPORTS%\Build-latest.log" >nul
>"%SAKURA_RELEASE_OUTPUT%\Build-Errors.md" echo # Sakura rebuild errors
>>"%SAKURA_RELEASE_OUTPUT%\Build-Errors.md" echo Build failed with exit code %SAKURA_BUILD_RESULT%. Log: %SAKURA_BUILD_LOG%
echo.
echo FAILED: Read %SAKURA_RELEASE_OUTPUT%\Build-Errors.md and the build log.
:finish
if not "%~1"=="--no-pause" pause
exit /b %SAKURA_BUILD_RESULT%
