@echo off
REM ============================================================
REM My Computer Dashboard - Windows build script
REM Produces dist\MyComputerDashboard.exe (no console window,
REM no Python installation required on the target machine).
REM ============================================================

setlocal

echo [1/4] Creating virtual environment (if needed)...
if not exist venv (
    python -m venv venv
)
call venv\Scripts\activate.bat

echo [2/4] Installing dependencies...
python -m pip install --upgrade pip >nul
pip install -r requirements.txt

echo [3/4] Cleaning previous build...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del /q MyComputerDashboard.spec 2>nul

echo [4/4] Building MyComputerDashboard.exe with PyInstaller...
pyinstaller ^
    --name "MyComputerDashboard" ^
    --onefile ^
    --windowed ^
    --noconsole ^
    --collect-submodules uvicorn ^
    --collect-submodules fastapi ^
    --hidden-import win32timezone ^
    main.py

if exist "dist\MyComputerDashboard.exe" (
    echo.
    echo Build succeeded: dist\MyComputerDashboard.exe
) else (
    echo.
    echo Build FAILED - see PyInstaller output above.
    exit /b 1
)

endlocal
