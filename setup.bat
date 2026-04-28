@echo off
echo ================================
echo  Review Collector - Setup
echo ================================
echo.

echo [1/2] Installing Python packages...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [!] pip install failed.
    pause
    exit /b 1
)

echo.
echo [2/2] Installing Playwright browser...
playwright install chromium
if %errorlevel% neq 0 (
    echo [!] Playwright install failed.
    pause
    exit /b 1
)

echo.
echo ================================
echo  Setup complete!
echo  Run: double-click 리뷰수집.hta
echo ================================
pause
