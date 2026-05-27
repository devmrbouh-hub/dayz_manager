@echo off
REM Сборка DayZ Server Manager в EXE

echo ========================================
echo   DayZ Server Manager - Build Script
echo ========================================
echo.

REM Проверить Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found!
    pause
    exit /b 1
)

REM Установить зависимости
echo [1/3] Installing dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)
echo.

REM Скомпилировать
echo [2/3] Building EXE...
pyinstaller --onefile --name "DayZManager" ^
    --add-data "web;web" ^
    --add-data "bercon-cli.exe;." ^
    --exclude-module PyQt5 ^
    --exclude-module PyQt6 ^
    --exclude-module PySide2 ^
    --exclude-module PySide6 ^
    --exclude-module matplotlib ^
    --exclude-module pygame ^
    --hidden-import src.core ^
    --hidden-import src.api ^
    --hidden-import src.notifications ^
    --hidden-import src.utils ^
    src\main.py

if %errorlevel% neq 0 (
    echo [ERROR] Build failed
    pause
    exit /b 1
)
echo.

REM Копировать конфиг
echo [3/3] Copying config...
if not exist "dist\config" mkdir "dist\config"
copy "config\config.json" "dist\config\config.json"
if not exist "dist\web" mkdir "dist\web"
xcopy "web" "dist\web" /E /I /Y
echo.

echo ========================================
echo   Build complete!
echo   EXE location: dist\DayZManager.exe
echo ========================================
echo.
pause
