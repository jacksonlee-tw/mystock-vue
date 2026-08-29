@echo off
setlocal

cd /d "%~dp0"
set "VENV_PYTHON=%CD%\.venv\Scripts\python.exe"

if not exist "%VENV_PYTHON%" (
    echo Creating project virtual environment...
    py -3.11 -m venv .venv 2>nul || py -3 -m venv .venv
    if errorlevel 1 goto :setup_failed
)

"%VENV_PYTHON%" -c "import fastapi, uvicorn, sqlalchemy, google.genai, anthropic" >nul 2>&1
if errorlevel 1 (
    echo Installing backend dependencies into project virtual environment...
    "%VENV_PYTHON%" -m pip install -r backend\requirements.txt
    if errorlevel 1 goto :setup_failed
)

if not exist "backend\.env" (
    copy /Y "backend\.env.example" "backend\.env" >nul
    echo Created backend\.env from backend\.env.example. Configure it before using optional services.
)

cd /d "%~dp0backend"
"%VENV_PYTHON%" main.py
exit /b %errorlevel%

:setup_failed
echo Failed to prepare the backend Python environment.
exit /b 1