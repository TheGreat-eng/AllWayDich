@echo off
title AWSDichTruyen 3D Studio
cd /d "%~dp0"
"C:\Program Files\Python312\python.exe" app.py
if errorlevel 1 (
    echo.
    echo Exited with error code. Trying default python...
    python app.py
)
pause
