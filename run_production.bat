@echo off
chcp 65001 >nul
echo ========================================
echo Starting Agentic Job Scraper - Production
echo ========================================
echo.

REM Check if Node.js is installed
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed or not in PATH
    echo Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

REM Check if Python is installed
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python from https://www.python.org/
    pause
    exit /b 1
)

echo [1/4] Building frontend...
cd frontend
if not exist node_modules (
    echo Installing frontend dependencies...
    call npm install
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install frontend dependencies
        pause
        exit /b 1
    )
)
call npm run build
if %errorlevel% neq 0 (
    echo [ERROR] Frontend build failed
    pause
    exit /b 1
)
echo Frontend build completed successfully
cd ..
echo.

echo [2/4] Installing backend dependencies...
cd backend
if not exist env (
    echo Creating Python virtual environment...
    python -m venv env
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
)

echo Activating virtual environment...
call env\Scripts\activate.bat

echo Installing Python packages...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install backend dependencies
    pause
    exit /b 1
)
echo Backend dependencies installed successfully
echo.

echo [3/4] Checking environment configuration...
if not exist .env (
    echo [WARNING] .env file not found, copying from .env.example
    copy .env.example .env
    echo Please edit .env file with your configuration before running
    pause
)
echo.

echo [4/4] Starting production server...
echo Server will run on http://localhost:8000
echo Press Ctrl+C to stop the server
echo.

REM Run with uvicorn in production mode
python -m uvicorn web_app:app --host 0.0.0.0 --port 8000 --workers 4 --log-level info

pause
