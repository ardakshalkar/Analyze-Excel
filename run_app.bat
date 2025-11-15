@echo off
echo ========================================
echo Starting Streamlit App
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python or use Anaconda Prompt
    pause
    exit /b 1
)

echo Python found!
python --version
echo.

REM Check if Streamlit is installed
python -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo WARNING: Streamlit is not installed
    echo Installing Streamlit...
    python -m pip install streamlit>=1.29.0
    echo.
)

REM Check Streamlit version
echo Checking Streamlit version...
python -c "import streamlit as st; print('Streamlit version:', st.__version__); print('Has st.dialog:', hasattr(st, 'dialog'))"
echo.

REM Check if .env file exists
if not exist .env (
    echo WARNING: .env file not found!
    echo Please create a .env file with your OPENAI_API_KEY
    echo Example: OPENAI_API_KEY=sk-your-key-here
    echo.
    pause
)

echo ========================================
echo Starting Streamlit server...
echo The app will open in your browser automatically
echo Press Ctrl+C to stop the server
echo ========================================
echo.

REM Run Streamlit
streamlit run app.py

pause

