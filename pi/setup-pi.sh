#!/usr/bin/env bash
# 作用：板子一键安装：apt 装 mosquitto、放 broker 配置、装两个 systemd、起服务并自检
# 树莓派 / 香橙派 一键准备（Ubuntu/Debian 系）
set -euo pipefail
echo "== 1/5 系统依赖"
sudo apt update
sudo apt install -y python3 python3-venv tzdata mosquitto mosquitto-clients

echo "== 2/5 打开局域网监听"
sudo mkdir -p /etc/mosquitto/conf.d
sudo cp "$(dirname "$0")/mosquitto.conf" /etc/mosquitto/conf.d/caremate.conf
sudo systemctl enable --now mosquitto
sudo systemctl restart mosquitto

echo "== 3/5 安装服务（脚本所在目录假定就是 /opt/caremate）"
sudo useradd -m -s /bin/bash caremate 2>/dev/null || true
sudo cp "$(dirname "$0")/caremate-server.service" /etc/systemd/system/
sudo cp "$(dirname "$0")/caremate-bridge.service" /etc/systemd/system/
sudo chown -R caremate:caremate /opt/caremate
sudo systemctl daemon-reload
sudo systemctl enable caremate-server caremate-bridge

echo "== 4/5 启动"
sudo systemctl restart caremate-server
sleep 2
sudo systemctl restart caremate-bridge
sleep 1

echo "== 5/5 自检"
curl -s http://127.0.0.1:8000/api/v1/health || echo "（服务没起来，看 journalctl -u caremate-server）"
echo
echo "订阅一条看看： mosquitto_sub -h 127.0.0.1 -t 'home/#' -v"

