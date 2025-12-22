@echo off
:: Switch to the directory where this script is located
cd /d "%~dp0"

echo [*] Launching System in: %CD%
python run_system.py

if %errorlevel% neq 0 (
    echo.
    echo [!] Error occurred. Press any key to exit...
    pause
)
