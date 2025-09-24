@echo off
echo Starting AI Assignment Checker Server...
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found!
    echo Please run setup.bat first.
    pause
    exit /b 1
)

REM Activate virtual environment and start server
call venv\Scripts\activate.bat
echo Virtual environment activated.
echo.
echo Starting Flask server...
echo Server will be available at: http://localhost:5000
echo Press Ctrl+C to stop the server.
echo.
python app.py

pause