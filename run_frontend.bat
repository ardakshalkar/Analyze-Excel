@echo off
echo Starting Vue.js frontend...
cd /d "%~dp0"
if not exist "frontend" (
    echo Error: frontend directory not found!
    pause
    exit /b 1
)
cd /d "%~dp0frontend"
if not exist "package.json" (
    echo Error: package.json not found in frontend directory!
    pause
    exit /b 1
)

echo Checking and installing dependencies...
if not exist "node_modules" (
    echo Installing dependencies...
    call npm install
    if errorlevel 1 (
        echo Error installing dependencies!
        pause
        exit /b 1
    )
) else (
    echo Dependencies found. Verifying installation...
    if not exist "node_modules\.bin\vite.cmd" (
        echo Vite not found. Reinstalling dependencies...
        call npm install
        if errorlevel 1 (
            echo Error installing dependencies!
            pause
            exit /b 1
        )
    )
)

echo Starting development server...
echo Current directory: %CD%
echo.
echo Using: npm run dev
echo.
call npm run dev
pause

