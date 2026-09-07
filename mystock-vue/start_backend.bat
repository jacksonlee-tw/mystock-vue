@echo off
REM Start the MyStock FastAPI backend with uv (see spec-review-ai/start_backend.bat).
REM uv owns the project .venv: it creates it and installs backend\requirements.txt into it.
setlocal

cd /d "%~dp0"

where uv >nul 2>&1
if errorlevel 1 goto :no_uv

set "VENV_DIR=%CD%\.venv"
REM Pin uv to the project .venv so `uv run --no-project` / `uv pip` never touch another env.
set "VIRTUAL_ENV=%VENV_DIR%"

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo Creating project virtual environment with uv...
    uv venv --python ">=3.11" "%VENV_DIR%"
    if errorlevel 1 goto :setup_failed
)

uv run --no-project python -c "import fastapi, uvicorn, sqlalchemy, google.genai, anthropic" >nul 2>&1
if errorlevel 1 (
    echo Installing backend dependencies with uv...
    uv pip install -r backend\requirements.txt
    if errorlevel 1 goto :setup_failed
)

if not exist "backend\.env" (
    copy /Y "backend\.env.example" "backend\.env" >nul
    echo Created backend\.env from backend\.env.example. Configure it before using optional services.
)

cd /d "%~dp0backend"
uv run --no-project main.py
exit /b %errorlevel%

:no_uv
echo uv was not found on PATH. Install it first, e.g. "winget install --id astral-sh.uv"
echo or see https://docs.astral.sh/uv/getting-started/installation/
exit /b 1

:setup_failed
echo Failed to prepare the backend Python environment.
exit /b 1
