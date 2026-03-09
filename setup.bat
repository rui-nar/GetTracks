@echo off
REM GetTracks Setup Script
REM Creates virtual environment and installs dependencies

echo Setting up GetTracks development environment...

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

echo Python found. Creating virtual environment...

REM Create virtual environment
python -m venv .venv
if errorlevel 1 (
    echo Error: Failed to create virtual environment
    pause
    exit /b 1
)

echo Virtual environment created. Installing dependencies...

REM Install dependencies using venv Python
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 (
    echo Warning: Failed to upgrade pip, continuing...
)

.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo Error: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo Setup complete! You can now:
echo - Run 'launch.bat' to start the application
echo - Or run '.venv\Scripts\python.exe -m pytest' to run tests
echo.
echo Remember to configure your Strava credentials in config.json
echo.

pause