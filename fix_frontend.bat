@echo off
echo ========================================
echo Fixing Frontend Installation
echo ========================================
echo.
echo This will clean and reinstall all frontend dependencies.
echo.
pause

cd /d "%~dp0frontend"
if not exist "package.json" (
    echo Error: package.json not found!
    pause
    exit /b 1
)

call reinstall.bat

echo.
echo ========================================
echo Fix complete! Starting frontend...
echo ========================================
echo.
call npm run dev

