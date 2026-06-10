@echo off
chcp 65001 >nul
echo Starting Agentic Job Scraper...
echo.

cd backend
call env\Scripts\activate.bat
python -m uvicorn web_app:app --host 0.0.0.0 --port 8000 --workers 4 --log-level info
