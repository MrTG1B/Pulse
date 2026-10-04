@echo off
echo ========================================================
echo  Pulse — Standalone Executable Build Script
echo ========================================================
python build_exe.py
if %ERRORLEVEL% NEQ 0 (
    echo [Error] Build failed!
    pause
    exit /b %ERRORLEVEL%
)
echo [Success] Executable created at dist\Pulse.exe
pause
