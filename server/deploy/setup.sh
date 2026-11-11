#!/usr/bin/env bash
# 作用：服务器一键部署：装依赖、建账号目录、生成/复用 .env 令牌、systemd、可选 Caddy、自检
# CareMate 一键部署（Ubuntu 22.04+，需 root）
#
# 用法：
#   sudo bash deploy/setup.sh --no-domain          # 只起服务，监听 0.0.0.0:8000（最快）
#   sudo bash deploy/setup.sh caremate.example.com # 加 Caddy 自动 HTTPS（A 记录要先指过来）
#
# 幂等：可以重复跑；已有 .env / 已有数据库都不会被覆盖。
set -euo pipefail

DOMAIN=""
NO_DOMAIN=0
if [[ "${1:-}" == "--no-domain" || -z "${1:-}" ]]; then
  NO_DOMAIN=1
else
  DOMAIN="$1"
fi

APP_DIR=/opt/caremate
SVC_USER=caremate
PORT=8000

if [[ $EUID -ne 0 ]]; then
  echo "请用 root 运行： sudo bash deploy/setup.sh [--no-domain | 你的域名]"
  exit 1
fi

echo "== 1/6 系统依赖"
apt-get update -qq
apt-get install -y -qq python3 python3-venv curl rsync ufw

echo "== 2/6 服务账号与目录"
id -u "$SVC_USER" >/dev/null 2>&1 || useradd -r -m -s /bin/bash "$SVC_USER"
mkdir -p "$APP_DIR"
rsync -a --exclude 'caremate.db*' --exclude '__pycache__' --exclude '.env' ./ "$APP_DIR/"
chown -R "$SVC_USER:$SVC_USER" "$APP_DIR"

echo "== 3/6 令牌（.env）"
if [[ -f "$APP_DIR/.env" ]]; then
  echo "   已有 $APP_DIR/.env，保留（要换就删了重跑本脚本）"
else
  python3 - "$APP_DIR/.env" <<'PY'
import secrets, sys
path = sys.argv[1]
lines = [
    "# 由 deploy/setup.sh 生成；不要提交到仓库",
    "CAREMATE_ELDER_TOKEN=" + secrets.token_urlsafe(24),
    "CAREMATE_FAMILY_TOKEN=" + secrets.token_urlsafe(24),
    "CAREMATE_COMMUNITY_TOKEN=" + secrets.token_urlsafe(24),
    "CAREMATE_PAIR_CODE=" + "".join(secrets.choice("0123456789") for _ in range(6)),
]
open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("   已生成 " + path)
PY
  chown "$SVC_USER" "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
  echo "   ---- 令牌（抄下来）----"
  sed 's/^/   /' "$APP_DIR/.env"
  echo "   ------------------------"
fi

echo "== 3.5/6 Python 虚拟环境（单元里的 ExecStart 指向 .venv）"
if [[ ! -x "$APP_DIR/.venv/bin/python" ]]; then
  sudo -u "$SVC_USER" python3 -m venv "$APP_DIR/.venv"
  sudo -u "$SVC_USER" "$APP_DIR/.venv/bin/pip" install -q --upgrade pip
  echo "   已建 $APP_DIR/.venv"
else
  echo "   已有 .venv，跳过"
fi

echo "== 4/6 systemd 单进程服务"
install -m 644 "$APP_DIR/deploy/caremate.service" /etc/systemd/system/caremate.service
if [[ $NO_DOMAIN -eq 1 ]]; then
  # 没有反代：服务直接对外监听，浏览器用 http://IP:8000
  sed -i "s/--host 127.0.0.1/--host 0.0.0.0/" /etc/systemd/system/caremate.service
fi
systemctl daemon-reload
systemctl enable --now caremate
sleep 2
if ! systemctl is-active --quiet caremate; then
  echo "   启动失败，看日志： journalctl -u caremate -n 50"
  exit 1
fi
echo "   服务已启动"

echo "== 5/6 防火墙与 HTTPS"
ufw allow 22/tcp >/dev/null 2>&1 || true
if [[ $NO_DOMAIN -eq 1 ]]; then
  ufw allow "$PORT/tcp" >/dev/null 2>&1 || true
  echo "   未绑域名：已放行 $PORT，入口 http://<服务器IP>:$PORT"
else
  ufw allow 80,443/tcp >/dev/null 2>&1 || true
  if ! command -v caddy >/dev/null 2>&1; then
    apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https gnupg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
      | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
      > /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -qq && apt-get install -y -qq caddy
  fi
  sed "s/caremate\.example\.com/$DOMAIN/g" "$APP_DIR/deploy/Caddyfile" > /etc/caddy/Caddyfile
  systemctl reload caddy 2>/dev/null || systemctl restart caddy
  echo "   已配置 Caddy：https://$DOMAIN"
fi
ufw --force enable >/dev/null 2>&1 || true

echo "== 6/6 备份定时任务"
mkdir -p /var/backups/caremate
if ! crontab -l 2>/dev/null | grep -q 'server.py --backup'; then
  (crontab -l 2>/dev/null || true
   echo "0 3 * * * cd $APP_DIR && python3 server.py --backup >> /var/log/caremate-backup.log 2>&1") | crontab -
  echo "   已加：每天 03:00 在线备份到 $APP_DIR/backups/"
else
  echo "   已有备份任务，跳过"
fi

echo "== 自检"
echo -n "   本机健康检查: "
curl -s --max-time 5 "http://127.0.0.1:$PORT/api/v1/health" || echo "（失败）"
echo ""
if [[ $NO_DOMAIN -eq 0 ]]; then
  echo -n "   公网健康检查: "
  curl -s --max-time 10 "https://$DOMAIN/api/v1/health" || echo "（证书可能还在申请，等 1 分钟看 journalctl -u caddy）"
  echo ""
  echo "完成。入口： https://$DOMAIN/   老人端 /app   看板 /dashboard   kiosk /kiosk"
else
  echo ""
  echo "完成。入口： http://<服务器公网IP>:$PORT/dashboard"
fi
echo "日志： journalctl -u caremate -f"
echo "令牌： $APP_DIR/.env"
echo "备份： $APP_DIR/backups/（每天 03:00）"
