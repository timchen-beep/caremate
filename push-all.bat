@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在推送 main 与三条归档分支（首次会弹出 GitHub 登录，请允许）...
git push origin main v1-web v2-qt v3-flash
echo.
echo 推送结束。按任意键关闭。
pause >nul