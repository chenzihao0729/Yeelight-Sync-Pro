@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

where pythonw >nul 2>&1
if not errorlevel 1 (
  start "" pythonw "%~dp0main.py"
  exit /b 0
)

where python >nul 2>&1
if not errorlevel 1 (
  start "" python "%~dp0main.py"
  exit /b 0
)

where pyw >nul 2>&1
if not errorlevel 1 (
  start "" pyw "%~dp0main.py"
  exit /b 0
)

where py >nul 2>&1
if not errorlevel 1 (
  start "" py "%~dp0main.py"
  exit /b 0
)

echo Python was not found. Please install Python 3.
pause
exit /b 1
