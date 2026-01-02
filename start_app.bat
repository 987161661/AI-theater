@echo off
setlocal

:: Disable CrewAI Telemetry and OpenTelemetry
set CREWAI_TELEMETRY_OPT_OUT=true
set OTEL_SDK_DISABLED=true

:: Switch to the directory where this script is located
cd /d "%~dp0"

echo ==================================================
echo       AI Theater Launcher
echo ==================================================
echo.

:: Check if the virtual environment python exists
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found at: %~dp0venv
    echo.
    echo Please make sure you have set up the environment correctly:
    echo 1. Open a terminal
    echo 2. Run: python -m venv venv
    echo 3. Run: venv\Scripts\pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo [INFO] Found virtual environment.
echo [INFO] Starting Streamlit app...
echo.

:: Run streamlit using the venv python directly
:: This avoids issues with PATH variables not updating correctly
"venv\Scripts\python.exe" -m streamlit run app.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] The application crashed or was closed with an error.
    echo.
    pause
) else (
    echo.
    echo [INFO] Application closed normally.
)

endlocal
