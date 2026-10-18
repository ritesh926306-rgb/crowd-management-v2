@echo off
echo ================================================================
echo Pushing Venue Crowd Management System to GitHub...
echo Repository: https://github.com/ritesh926306-rgb/venue-crowd-management
echo ================================================================
echo.
echo If a GitHub Sign-In window appears, click "Sign in with your browser"
echo.
git push -u origin main
echo.
if %ERRORLEVEL% EQU 0 (
    echo [SUCCESS] Code and GitHub Actions pipeline pushed to GitHub!
    echo Visit: https://github.com/ritesh926306-rgb/venue-crowd-management/actions
) else (
    echo [ERROR] Push failed. Please verify your GitHub login credentials.
)
pause
