@echo off
REM 作用：开机/登录时静默拉起 CareMate 后端（配合 Tailscale Funnel 提供固定公网地址）
REM 说明：先读取 server\.env 里的令牌/配对码（不存在则用演示值）；用 pythonw 不弹窗
setlocal enableextensions
cd /d "%~dp0"

if exist "%~dp0.env" (
  for /f "usebackq tokens=1,* delims==" %%A in ("%~dp0.env") do (
    set "line=%%A"
    if not "!line:~0,1!"=="#" if not "%%A"=="" set "%%A=%%B"
  )
)

start "" /min "C:\Users\43915\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\pythonw.exe" server.py --port 8000 >> "%~dp0server.log" 2>&1
endlocal