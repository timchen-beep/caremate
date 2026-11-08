@REM 作用：Windows 本地启动器：ASCII 输出，避免中文代码页乱码
@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title CareMate server

echo ==================================================
echo   CareMate  -  cloud + app + dashboard
echo   Folder: %cd%
echo ==================================================
echo.

rem ---------------------------------------------------------------
rem  Already running?  Ask the API instead of trusting netstat
rem  (Windows can show stale LISTENING rows with PID 0).
rem ---------------------------------------------------------------
set "CODE="
for /f "delims=" %%c in ('curl -s -o nul -w "%%{http_code}" --max-time 2 http://127.0.0.1:8000/api/v1/health 2^>nul') do set "CODE=%%c"
if "%CODE%"=="200" (
  echo   A CareMate server is ALREADY running on port 8000.
  echo   Opening it in the browser. Close that old window for a fresh start.
  echo.
  start "" http://127.0.0.1:8000/
  timeout /t 3 >nul
  exit /b 0
)

rem ---------------------------------------------------------------
rem  Find a working python.exe (skip the Microsoft Store alias)
rem ---------------------------------------------------------------
set "PY="

for /f "delims=" %%p in ('where python 2^>nul') do (
  if not defined PY (
    echo %%p | findstr /i "WindowsApps" >nul
    if errorlevel 1 (
      "%%p" -c "import sys" >nul 2>nul
      if not errorlevel 1 set "PY=%%p"
    )
  )
)

if not defined PY (
  for %%d in ("%LOCALAPPDATA%\Programs\Python" "%LOCALAPPDATA%\Python" "%ProgramFiles%\Python" "%ProgramFiles(x86)%\Python") do (
    if exist "%%~d" (
      for /d %%i in ("%%~d\Python*") do (
        if not defined PY if exist "%%~i\python.exe" set "PY=%%~i\python.exe"
      )
      for /d %%i in ("%%~d\pythoncore*") do (
        if not defined PY if exist "%%~i\python.exe" set "PY=%%~i\python.exe"
      )
    )
  )
)

if not defined PY (
  for /f "delims=" %%p in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do (
    if not defined PY if exist "%%p" set "PY=%%p"
  )
)

if not defined PY (
  echo [ERROR] No working python.exe found.
  echo.
  echo The "python" on your PATH is probably the Microsoft Store alias
  echo under WindowsApps, which fails when executed.
  echo.
  echo Fix, any one of these:
  echo   1. Install Python 3 from python.org, tick "Add python.exe to PATH"
  echo   2. Settings - Apps - Advanced app settings - App execution aliases:
  echo      turn OFF python.exe and python3.exe, then re-run this file
  echo   3. If you know the path, run it directly:
  echo      "C:\path\to\python.exe" server.py --host 0.0.0.0 --port 8000
  echo.
  pause
  exit /b 1
)

echo   Python: %PY%
echo.

echo   Home      http://127.0.0.1:8000/
echo   App       http://127.0.0.1:8000/app
echo   Web       http://127.0.0.1:8000/dashboard
echo.
echo   Phone:    same Wi-Fi, open http://YOUR-PC-IP:8000/app
echo   Close this window to stop the server.
echo ==================================================
echo.

start "" http://127.0.0.1:8000/
"%PY%" server.py --host 0.0.0.0 --port 8000
echo.
echo Server stopped.
pause

