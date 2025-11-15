@echo off
echo ========================================
echo Cleaning and reinstalling dependencies
echo ========================================
cd /d "%~dp0"
echo Current directory: %CD%
echo.

if exist "node_modules" (
    echo Removing old node_modules...
    rmdir /s /q node_modules
    if errorlevel 1 (
        echo Warning: Could not fully remove node_modules. Trying again...
        timeout /t 2 /nobreak >nul
        rmdir /s /q node_modules
    )
    echo Done.
)

if exist "package-lock.json" (
    echo Removing package-lock.json...
    del /q package-lock.json
)

echo.
echo Installing fresh dependencies...
echo This may take a few minutes...
call npm install --force
if errorlevel 1 (
    echo.
    echo Error installing dependencies!
    echo Try running: npm cache clean --force
    pause
    exit /b 1
)

echo.
echo ========================================
echo Dependencies installed successfully!
echo ========================================
echo.
echo You can now run the frontend with:
echo   - From root: run_frontend.bat
echo   - From here: npm run dev
echo.
pause

