@echo off
echo ================================================================
echo Pushing Venue Crowd Management System to NEW REPOSITORY:
echo Repository: https://github.com/ritesh926306-rgb/crowd-management-v2
echo ================================================================
echo.
echo Make sure you created the empty repo at: https://github.com/new
echo with Repository name: crowd-management-v2
echo.
echo If a GitHub Sign-In window appears, click "Sign in with your browser"
echo.
git push -u origin main
echo.
if %ERRORLEVEL% EQU 0 (
    echo [SUCCESS] Code and GitHub Actions pipeline pushed to NEW REPOSITORY!
    echo Visit: https://github.com/ritesh926306-rgb/crowd-management-v2/actions
) else (
    echo [ERROR] Push failed. Make sure you created the repo crowd-management-v2 on GitHub!
)
pause
