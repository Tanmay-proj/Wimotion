@echo off
echo ========================================================
echo   WiMotion v1 - Reading Full 4MB Flash from COM8 & COM9
echo ========================================================
echo.
echo [*] Dumping COM8 (Original RX) to original_rx_com8.bin...
py -3.10 -m esptool --chip esp32 --port COM8 --baud 921600 read_flash 0x0 0x400000 "%~dp0original_rx_com8.bin"
if errorlevel 1 (
    echo [FAIL] Failed to dump COM8!
    pause
    exit /b 1
)
echo [+] COM8 successfully dumped!
echo.

echo [*] Dumping COM9 (Original TX) to original_tx_com9.bin...
py -3.10 -m esptool --chip esp32 --port COM9 --baud 921600 read_flash 0x0 0x400000 "%~dp0original_tx_com9.bin"
if errorlevel 1 (
    echo [FAIL] Failed to dump COM9!
    pause
    exit /b 1
)
echo [+] COM9 successfully dumped!
echo.
echo ========================================================
echo   [SUCCESS] Both boards backed up 100%% bit-by-bit!
echo ========================================================
pause
