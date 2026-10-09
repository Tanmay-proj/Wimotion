@echo off
echo ========================================================
echo   WiMotion v1 - 1-Click Original Hardware Restorer
echo ========================================================
echo.
echo Checking for COM8 (Original RX) and COM9 (Original TX)...
echo.

if not exist "%~dp0original_rx_com8.bin" (
    echo [ERROR] original_rx_com8.bin not found in this folder!
    pause
    exit /b 1
)

if not exist "%~dp0original_tx_com9.bin" (
    echo [ERROR] original_tx_com9.bin not found in this folder!
    pause
    exit /b 1
)

echo [*] Flashing Original RX on COM8...
py -3.10 -m esptool --chip esp32 --port COM8 --baud 921600 write_flash 0x0 "%~dp0original_rx_com8.bin"
if errorlevel 1 (
    echo [FAIL] Failed to flash RX on COM8!
    pause
    exit /b 1
)
echo [+] RX successfully restored on COM8!
echo.

echo [*] Flashing Original TX on COM9...
py -3.10 -m esptool --chip esp32 --port COM9 --baud 921600 write_flash 0x0 "%~dp0original_tx_com9.bin"
if errorlevel 1 (
    echo [FAIL] Failed to flash TX on COM9!
    pause
    exit /b 1
)
echo [+] TX successfully restored on COM9!
echo.
echo ========================================================
echo   [SUCCESS] Both WiMotion v1 boards restored 100%%!
echo ========================================================
pause
