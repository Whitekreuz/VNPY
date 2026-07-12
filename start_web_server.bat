@echo off
title Moderixest Trade Web Server
echo ==================================================
echo         Moderixest Trade Web Server Launcher
echo ==================================================
echo.
cd /d "%~dp0"

set PYTHON_PATH=D:\miniconda3\envs\quant\python.exe

if not exist "%PYTHON_PATH%" (
    echo [WARNING] Conda environment Python not found at %PYTHON_PATH%
    echo Trying fallback to system "python" command...
    set PYTHON_PATH=python
)

echo Starting web server using: %PYTHON_PATH%
echo Press Ctrl+C to stop the server.
echo.

"%PYTHON_PATH%" scripts/web_server.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Web server stopped with error code %ERRORLEVEL%.
    pause
)
