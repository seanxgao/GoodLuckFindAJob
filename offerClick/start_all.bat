@echo off
echo Starting OfferClick Full Stack...

:: Start Backend in a new window
start "OfferClick Backend" cmd /k "call start_backend.bat"

:: Wait a moment for backend to initialize
timeout /t 2 /nobreak >nul

:: Start Frontend in a new window
start "OfferClick Frontend" cmd /k "call start_frontend.bat"

echo Both services started!

