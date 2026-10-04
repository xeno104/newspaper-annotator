@echo off
title Newspaper Intelligence Hub
color 0b

echo ==================================================
echo    Newspaper Intelligence Hub is starting...
echo ==================================================
echo.

:: 1. DETECT THE CORRECT PYTHON COMMAND
set PYTHON_CMD=
where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set PYTHON_CMD=python
) else (
    where python3 >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        set PYTHON_CMD=python3
    )
)

:: 2. IF NO PYTHON IS FOUND, THROW AN ERROR
if "%PYTHON_CMD%"=="" (
    color 0c
    echo [ERROR] Python is not installed or not added to your system PATH!
    echo Please install Python 3 from python.org and ensure you check the box
    echo that says "Add Python to PATH" during installation.
    echo.
    pause
    exit /b
)

echo [SUCCESS] Found Python executable: %PYTHON_CMD%
echo.

:: 3. INSTALL DEPENDENCIES USING THE DETECTED PYTHON
echo Checking dependencies (this takes a moment on first run)...
%PYTHON_CMD% -m pip install -r requirements.txt --quiet

echo.
echo Launching the server and opening your browser...
echo.
echo NOTE: Keep this black window open while using the app!
echo To quit, simply close this window.
echo.

:: 4. START THE APP
%PYTHON_CMD% app.py

pause