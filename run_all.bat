@echo off
echo ========================================
echo Starting Analyze & Excel - All Services
echo ========================================
echo.
echo This will start:
echo 1. FastAPI Backend (port 8000)
echo 2. Vue.js Frontend (port 5173)
echo.
echo Streamlit app can be started separately with: run_app.bat
echo.
echo Press Ctrl+C to stop all services
echo.

start "FastAPI Backend" cmd /k "cd /d %~dp0 && python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000"
timeout /t 3 /nobreak >nul
start "Vue.js Frontend" cmd /k "cd /d %~dp0frontend && npx vite"

echo.
echo Services started! Check the opened windows for status.
echo.
echo FastAPI: http://localhost:8000
echo FastAPI Docs: http://localhost:8000/docs
echo Vue.js Frontend: http://localhost:5173
echo.
pause

