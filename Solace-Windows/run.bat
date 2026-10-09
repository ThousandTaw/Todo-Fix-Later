@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
    set "SOLACE_PY=python"
) else (
    set "SOLACE_PY=py -3"
)
if not exist ".venv\Scripts\python.exe" (
    %SOLACE_PY% -m venv .venv
    if errorlevel 1 goto failure
)
".venv\Scripts\python.exe" -c "import cryptography, customtkinter, PIL" >nul 2>nul
if errorlevel 1 (
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto failure
)
".venv\Scripts\python.exe" app.py
if errorlevel 1 goto failure
exit /b 0
:failure
echo Install Python 3.11 or newer with Tcl/Tk and pip. Read the error above.
pause
exit /b 1
