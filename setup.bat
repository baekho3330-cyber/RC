@echo off
echo ================================
echo  Review Fetch - Setup
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
echo [3/3] Building executable...
pyinstaller ReviewFetch.spec --noconfirm
if %errorlevel% neq 0 (
    echo [!] Build failed.
    pause
    exit /b 1
)

echo.
echo ================================
echo  Build complete!
echo  Run: dist\ReviewFetch\ReviewFetch.exe
echo ================================
pause
