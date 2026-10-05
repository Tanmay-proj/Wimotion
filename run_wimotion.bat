@echo off
REM ==============================================================================
REM WiMotion v2.4 - Launcher
REM Ensures the working directory is always the project root (where this .bat lives)
REM Models were trained with scikit-learn on Python 3.10, so we prefer that version.
REM ==============================================================================
cd /d "%~dp0"

REM Try Python 3.10 first (models are compatible), then fall back to any available Python
py -3.10 --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    py -3.10 wimotion_main.py %*
) else (
    echo [!] Python 3.10 not found. Trying default python...
    echo [!] Note: ML models may not load due to version mismatch, but heuristic mode will work.
    python wimotion_main.py %*
)
pause