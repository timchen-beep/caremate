#!/usr/bin/env bash
# CareMate 一键部署（Ubuntu 22.04+，需 root）
# 用法：sudo bash deploy/setup.sh caremate.example.com
set -euo pipefail

DOMAIN="${1:-}"
APP_DIR=/opt/caremate
SVC_USER=caremate

if [[ $EUID -ne 0 ]]; then
  echo "请用 root 运行： sudo bash deploy/setup.sh <你的域名>"
  exit 1
fi
if [[ -z "$DOMAIN" ]]; then
  echo "缺少域名。示例： sudo bash deploy/setup.sh caremate.example.com"
  exit 1
fi

echo "== 1/6 系统依赖"
apt-get update -qq
apt-get install -y -qq python3 python3-venv curl rsync

echo "== 2/6 服务账号与目录"
id -u "$SVC_USER" >/dev/null 2>&1 || useradd -m -s /bin/bash "$SVC_USER"
mkdir -p "$APP_DIR"
rsync -a --exclude 'caremate.db*' --exclude '__pycache__' ./ "$APP_DIR/"
chown -R "$SVC_USER:$SVC_USER" "$APP_DIR"

echo "== 3/6 Python 环境（本项目零第三方依赖）"
sudo -u "$SVC_USER" python3 -m venv "$APP_DIR/.venv"
sudo -u "$SVC_USER" "$APP_DIR/.venv/bin/pip" install -q --upgrade pip

echo "== 4/6 systemd 单进程服务"
install -m 644 "$APP_DIR/deploy/caremate.service" /etc/systemd/system/caremate.service
systemctl daemon-reload
systemctl enable --now caremate
sleep 2
systemctl is-active --quiet caremate && echo "   服务已启动" || { echo "   启动失败，看日志： journalctl -u caremate -n 50"; exit 1; }

echo "== 5/6 Caddy（自动 TLS）"
if ! command -v caddy >/dev/null 2>&1; then
  apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https gnupg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -qq && apt-get install -y -qq caddy
fi
sed "s/caremate\.example\.com/$DOMAIN/g" "$APP_DIR/deploy/Caddyfile" > /etc/caddy/Caddyfile
systemctl reload caddy || systemctl restart caddy

echo "== 6/6 自检"
sleep 2
echo -n "   本机健康检查: "
curl -s --max-time 5 http://127.0.0.1:8000/api/v1/health || echo "（失败）"
echo ""
echo -n "   公网健康检查: "
curl -s --max-time 8 "https://$DOMAIN/api/v1/health" || echo "（证书可能还在申请，等 1 分钟再看 caddy 日志）"
echo ""
echo ""
echo "完成。入口： https://$DOMAIN/   老人端 /app   看护端 /dashboard"
echo "日志： journalctl -u caremate -f      /var/log/caddy/caremate.log"
echo "备份： sqlite3 $APP_DIR/caremate.db \".backup /var/backups/caremate-\$(date +%F).db\""
