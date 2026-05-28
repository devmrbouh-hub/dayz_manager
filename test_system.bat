@echo off
REM Тестирование DayZ Server Manager

echo ========================================
echo   DayZ Manager - System Tests
echo ========================================
echo.

if not defined API_KEY (
    echo [FAIL] Set API_KEY first, e.g. set API_KEY=your_key_from_config.json
    pause
    exit /b 1
)
if not defined BASE_URL set BASE_URL=http://localhost:8000
if not defined SERVER_ID set SERVER_ID=server1

REM Проверка что менеджер запущен
echo [1/5] Checking if manager is running...
curl -s %BASE_URL%/api/servers >nul 2>&1
if %errorlevel% neq 0 (
    echo [FAIL] Manager is not running!
    echo Start with: python src/main.py
    pause
    exit /b 1
)
echo [OK] Manager is running
echo.

REM Проверка API ключа
echo [2/5] Testing API authentication...
curl -s -H "X-API-Key: %API_KEY%" %BASE_URL%/api/servers | findstr "servers" >nul
if %errorlevel% neq 0 (
    echo [FAIL] API key authentication failed
    pause
    exit /b 1
)
echo [OK] API key works
echo.

REM Тест RCON
echo [3/5] Testing RCON connection...
curl -s -X POST -H "X-API-Key: %API_KEY%" %BASE_URL%/api/servers/%SERVER_ID%/rcon/test > temp_rcon.json
findstr "success" temp_rcon.json | findstr "true" >nul
if %errorlevel% neq 0 (
    echo [WARN] RCON test failed or disabled
    type temp_rcon.json
) else (
    echo [OK] RCON connection successful
)
del temp_rcon.json
echo.

REM Проверка модов
echo [4/5] Checking mod updates...
curl -s -X POST -H "X-API-Key: %API_KEY%" %BASE_URL%/api/mods/check > temp_mods.json
echo [INFO] Mod check result:
type temp_mods.json
del temp_mods.json
echo.

REM Проверка статусов серверов
echo [5/5] Getting server statuses...
curl -s -H "X-API-Key: %API_KEY%" %BASE_URL%/api/servers
echo.
echo.

echo ========================================
echo   Tests complete!
echo ========================================
pause
