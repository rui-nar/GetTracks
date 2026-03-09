@echo off
REM GetTracks Launcher
REM This script sets up the virtual environment and launches the application

echo Starting GetTracks...

REM Check if virtual environment exists
if not exist ".venv\Scripts\python.exe" (
    echo Error: Virtual environment not found at .venv
    echo Please run: python -m venv .venv
    echo Then: .venv\Scripts\python.exe -m pip install -r requirements.txt
    echo Or simply run: setup.bat
    pause
    exit /b 1
)

REM Check if main.py exists
if not exist "main.py" (
    echo Error: main.py not found
    pause
    exit /b 1
)

REM Check if config.json exists and has Strava credentials
if not exist "config.json" (
    echo Warning: config.json not found
    echo Please create config.json with your Strava credentials
    echo See README.md for details
)

REM Set Python path for src modules and use venv Python directly
set PYTHONPATH=%CD%\src
set PYTHONHOME=
set PYTHONEXECUTABLE=%CD%\.venv\Scripts\python.exe

REM Launch the application using venv Python
echo Launching GetTracks GUI...
echo If the application doesn't start, you may need a display environment.
echo.
.venv\Scripts\python.exe main.py

REM Check exit code
if %errorlevel% neq 0 (
    echo.
    echo Application exited with error code %errorlevel%
    echo This may be normal if running in a headless environment.
)

echo GetTracks session ended.
pause