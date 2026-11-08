<!-- 作用：部署说明：Caddy + systemd 的单机方案 -->
# CareMate 部署（反向代理 + 自动 TLS + 单 worker）

对应《Opening Report 4.2.6》最后一段：**反向代理终止 TLS，应用只跑一个进程**（SQLite 单写，多 worker 会互相踩）。

## 一、目标形态

```
浏览器/App ──HTTPS──▶ Caddy（自动证书，80/443）
                        │ 反向代理到 127.0.0.1:8000
                        ▼
                   server.py（单进程，含 30s 调度线程）
                        │
                        ▼
                   caremate.db（WAL，本机磁盘）
```

- 证书由 Caddy 自动申请、自动续期（需要域名 A 记录指向本机公网 IP，80/443 可入）。
- 应用只监听 127.0.0.1，不暴露到公网。
- `CAREMATE_WORKERS` 概念上恒为 1：不要用 gunicorn 多 worker 跑它，调度器会重复触发。

## 二、服务器准备（Ubuntu 22.04，1 核 2 G）

```bash
sudo apt update && sudo apt install -y python3.11 python3-venv git curl
sudo useradd -m -s /bin/bash caremate
sudo mkdir -p /opt/caremate && sudo chown caremate:caremate /opt/caremate
```

把 `caremate-cloud/` 整个目录上传到 `/opt/caremate/`（scp / rsync / git clone 均可）。

## 三、装依赖并试跑

```bash
cd /opt/caremate
python3 -m venv .venv
. .venv/bin/activate
# 本项目零第三方依赖；若换成 paho-mqtt / psycopg 再 pip install
CAREMATE_MODE=cloud \
CAREMATE_TZ=Asia/Shanghai \
CAREMATE_JWT_SECRET=$(openssl rand -hex 16) \
python server.py --host 127.0.0.1 --port 8000
```

看到「调度器 开」即可 Ctrl+C，交给 systemd 托管。

## 四、systemd（单进程 + 自动重启）

```bash
sudo cp deploy/caremate.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now caremate
sudo systemctl status caremate --no-pager
journalctl -u caremate -f          # 看调度器日志
```

## 五、Caddy 反代 + 自动 TLS

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy
```

把 `Caddyfile` 里的域名换成你的，然后：

```bash
sudo cp deploy/Caddyfile /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

打开 `https://你的域名/` 应看到两个入口；`/app` 是老人端，`/dashboard` 是看护端。

## 六、验证

```bash
curl -s https://你的域名/api/v1/health | python3 -m json.tool
# {"ok": true, "version": "0.5.0", "scheduler": true, "tz": "Asia/Shanghai", ...}

# 跨家庭越权必须是 403
curl -s -o /dev/null -w '%{http_code}\n' -H 'X-Token: comm-demo-2026' \
  'https://你的域名/api/v1/occurrences?user_id=u-elder'

# 重启 10 次不丢不重（在服务器上跑）
python3 test_accept.py
```

## 七、成本与边界

| 项 | 数量 | 说明 |
|---|---|---|
| 云主机 | 1 核 2 G | 学生机 50–100 元/月；演示可用免费额度 |
| 带宽 | 1–3 Mbps | 文本与 JSON 为主，够用 |
| 存储 | 10 G | 一年记录量级远小于此 |
| 可用性 | 无 SLA | 单机单进程，重启有秒级中断；**不承诺 7×24**，与文档一致 |

## 八、上云前必改的三项

1. **把演示令牌换掉**：直接改 `init_db()` 里的 `token`，或只用配对码换来的会话令牌。
2. **数据库口令/路径**：`CAREMATE_DB` 指向挂载盘；换 PostgreSQL 时只需重写 `connect()`。
3. **备份**：`sqlite3 caremate.db ".backup /backup/caremate-$(date +%F).db"` 放进 cron，每天一次。

<!-- 文件：caremate-cloud/deploy/README.md -->
