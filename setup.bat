@echo off
echo ======================================
echo AI Assignment Checker - Windows Setup
echo ======================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.9+ from https://python.org
    pause
    exit /b 1
)

echo Python found. Running setup script...
echo.

python setup.py

if errorlevel 1 (
    echo.
    echo Setup encountered errors. Please check the output above.
    pause
    exit /b 1
)

echo.
echo ======================================
echo Setup completed successfully!
echo ======================================
echo.
echo To start the application:
echo 1. Double-click 'start_server.bat' 
echo 2. OR manually run:
echo    venv\Scripts\activate
echo    python app.py
echo.
pause