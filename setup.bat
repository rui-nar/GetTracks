@echo off
REM GetTracks Setup Script
REM This script sets up the virtual environment and installs dependencies

echo.
echo ========================================
echo GetTracks - Setup Script
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.9+ from https://www.python.org/
    pause
    exit /b 1
)

REM Check if virtual environment already exists
if exist ".venv" (
    echo Virtual environment already exists.
    echo Skipping venv creation.
) else (
    echo Creating virtual environment...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo Error: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo ✓ Virtual environment created
)

echo.
echo Installing dependencies...
.venv\Scripts\python.exe -m pip install --upgrade pip >nul
.venv\Scripts\python.exe -m pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo Error: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo ========================================
echo ✓ Setup Complete!
echo ========================================
echo.
echo You can now launch GetTracks by running:
echo   launch.bat
echo or
echo   .venv\Scripts\python.exe main.py
echo.
pause
