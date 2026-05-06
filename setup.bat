@echo off
echo ================================
echo  Review Collector - Setup
echo ================================
echo.

echo [1/3] Installing Python packages...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [!] pip install failed.
    pause
    exit /b 1
)

echo.
echo [2/3] Installing Playwright browser...
playwright install chromium
if %errorlevel% neq 0 (
    echo [!] Playwright install failed.
    pause
    exit /b 1
)

echo.
echo [3/3] Creating shortcut...
powershell -Command "$ws=New-Object -ComObject WScript.Shell; $sc=$ws.CreateShortcut('%~dp0리뷰수집.lnk'); $sc.TargetPath='%~dp0리뷰수집.hta'; $sc.IconLocation='%~dp0icon.ico,0'; $sc.Description='Review Collector'; $sc.Save()"

echo.
echo ================================
echo  Setup complete!
echo  Run: double-click 리뷰수집.lnk
echo ================================
pause
