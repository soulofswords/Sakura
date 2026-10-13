@echo off
setlocal
cd /d "%~dp0"
"venv\Scripts\python.exe" "tools\build_bytecode.py"
if errorlevel 1 (
  echo Bytecode compilation failed. See tools\bytecode-build\Bytecode-Errors.md
  exit /b 1
)
echo Bytecode compilation completed. Editable source files were preserved.
