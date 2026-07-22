@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0my-project"

set "UVICORN=..\.venv\Scripts\uvicorn.exe"
set "PORT=8006"
set "URL=http://127.0.0.1:%PORT%/login"

if not exist "%UVICORN%" (
  echo [ERROR] Virtual env not found. Run once:
  echo   cd %~dp0
  echo   python -m venv .venv
  echo   .venv\Scripts\pip install -r requirements.txt
  pause
  exit /b 1
)

:: If server already running, just open browser
powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri 'http://127.0.0.1:%PORT%/health' -UseBasicParsing -TimeoutSec 2).StatusCode } catch { exit 1 }" >nul 2>&1
if %errorlevel%==0 (
  echo LUNA is already running. Opening browser...
  start "" "%URL%"
  exit /b 0
)

echo Starting LUNA server on %URL%
echo Close the "LUNA Server" window to stop.
start "LUNA Server" /D "%~dp0my-project" "%UVICORN%" main:app --host 127.0.0.1 --port %PORT%

timeout /t 3 /nobreak >nul
start "" "%URL%"

endlocal
