@echo off
title Build Pulse Executable
cd /d "%~dp0\.."
echo ========================================================
echo  Pulse — Standalone Executable Build Script
echo ========================================================
python scripts\build_exe.py
if %ERRORLEVEL% NEQ 0 (
    echo [Error] Build failed!
    pause
    exit /b %ERRORLEVEL%
)
echo [Success] Executable created at dist\Pulse.exe
pause
