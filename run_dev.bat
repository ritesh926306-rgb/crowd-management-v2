@echo off
echo ===================================================
echo Starting Venue Entry and Crowd Management System...
echo ===================================================
if exist venv\Scripts\python.exe (
    venv\Scripts\python.exe backend\app.py
) else (
    python backend\app.py
)
pause
