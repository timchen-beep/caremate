@echo off
REM 作用：开机/登录时静默拉起 CareMate 后端（配合 Tailscale Funnel 提供固定公网地址）
REM .env 由 server.py 自己读取，这里只负责静默启动并把输出写进 server.log
cd /d "%~dp0"
start "" /min "C:\Users\43915\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\pythonw.exe" server.py --port 8000
