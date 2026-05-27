@echo off
REM Установка DayZ Server Manager как службы Windows

echo ========================================
echo   DayZ Server Manager - Install Service
echo ========================================
echo.

REM Проверить NSSM
where nssm >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] NSSM not found!
    echo Download from: https://nssm.cc/download
    echo Extract and add to PATH
    pause
    exit /b 1
)

REM Получить путь к EXE
set EXE_PATH=%~dp0dist\DayZManager.exe

if not exist "%EXE_PATH%" (
    echo [ERROR] DayZManager.exe not found!
    echo Run build.bat first
    pause
    exit /b 1
)

REM Установить службу
echo Installing service...
nssm install DayZManager "%EXE_PATH%"
nssm set DayZManager AppDirectory "%~dp0dist"
nssm set DayZManager DisplayName "DayZ Server Manager"
nssm set DayZManager Description "Manages DayZ servers with auto-restart and mod updates"
nssm set DayZManager Start SERVICE_AUTO_START

REM Запустить службу
echo Starting service...
nssm start DayZManager

REM Открыть порт в фаерволе
echo Opening firewall port 8000...
netsh advfirewall firewall add rule name="DayZManager" dir=in action=allow protocol=TCP localport=8000

echo.
echo ========================================
echo   Service installed and started!
echo   Web UI: http://localhost:8000
echo ========================================
echo.
pause
