@echo off
REM 作用：开机/登录时静默拉起 CareMate 后端（配合 Tailscale Funnel 提供固定公网地址）
REM 说明：用 pythonw 才不会弹黑窗；日志写到 server\server.log
cd /d "%~dp0"
start "" /min "C:\Users\43915\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\pythonw.exe" server.py --port 8000 >> "%~dp0server.log" 2>&1