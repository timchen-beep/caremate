# 作用：把本机 CareMate 服务挂到固定域名的操作手册（Cloudflare 命名隧道），含每步命令与排错
# 固定域名上线：Cloudflare 命名隧道

> 目标：`https://caremate.你的域名.com/dashboard` 这种**地址固定、重启不变**的入口，
> 不需要租服务器、不需要公网 IP，电脑开着就能访问。

## 0. 前提（三条，缺一不可）

| 前提 | 说明 |
|---|---|
| Cloudflare 账号 | 免费注册：https://dash.cloudflare.com/sign-up |
| 一个域名，且已托管在 Cloudflare | 域名在别处买也行，把 NS 改成 Cloudflare 给的两条即可（生效几分钟到几小时） |
| cloudflared | 本机已装（`winget install Cloudflare.cloudflared`），路径 `C:\Program Files (x86)\cloudflared\cloudflared.exe` |

> 没有域名的话这条路线走不通——Cloudflare 命名隧道必须绑定自己账号下的 zone。
> 备选：买个 `.top`/`.xyz` 域名约 ¥10/年；或用快速隧道（地址随机、重启就变）。

## 1. 授权本机（一次性）

```powershell
& "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel login
```

会打开浏览器让你登录并选择域名。成功后本机生成：

```
%USERPROFILE%\.cloudflared\cert.pem        ← 账号凭据（不要提交到仓库）
```

## 2. 创建隧道

```powershell
& "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel create caremate
```

输出里有一行 `Created tunnel caremate with id <TUNNEL_ID>`，同时生成
`%USERPROFILE%\.cloudflared\<TUNNEL_ID>.json`（隧道凭据）。

## 3. 写配置

把仓库里的模板复制过去改三处：

```powershell
$dir = "$env:USERPROFILE\.cloudflared"
Copy-Item "C:\Users\43915\Documents\GitHub\main\tools\cloudflared-config.yml.template" "$dir\config.yml"
notepad "$dir\config.yml"     # 改 tunnel / credentials-file / hostname
```

关键点（踩过的坑都在这）：

- `service: http://127.0.0.1:8000` —— **不要写 localhost**。Windows 上 `localhost` 可能解析到
  `::1`，而我们的服务只监听 IPv4，表现就是隧道起来了但访问一律 502。
- `protocol: http2` —— 如果你们网络对 Cloudflare 的 QUIC（UDP 7844）不通（日志里
  `failed to dial to edge with quic: timeout`），必须走 http2（TCP 443）。我实测：QUIC 被墙、http2 正常。
- `hostname` 要和你第 4 步绑定的一致。

## 4. 绑定域名

```powershell
& "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel route dns caremate caremate.你的域名.com
```

它会在 Cloudflare 里自动加一条 CNAME（指向 `<TUNNEL_ID>.cfargotunnel.com`）。

## 5. 前台跑一次，确认通了

```powershell
& "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel run caremate
```

另开一个窗口验证：

```powershell
curl.exe -I https://caremate.你的域名.com/dashboard
curl.exe    https://caremate.你的域名.com/api/v1/health
```

看到 `HTTP/1.1 200` 和 `{"ok": true, ...}` 就成了。**同时确认本机服务在跑**：

```powershell
cd C:\Users\43915\Documents\GitHub\main\server
python server.py --port 8000
```

## 6. 装成开机自启（这样才是"随时能上"）

```powershell
& "C:\Program Files (x86)\cloudflared\cloudflared.exe" --config "$env:USERPROFILE\.cloudflared\config.yml" service install
```

装完它是 **Windows 服务**，开机自启、退出登录也不停。查状态：

```powershell
Get-Service cloudflared
Start-Service cloudflared      # 或 Stop-Service / Restart-Service
```

本机服务也要开机自启（任选一种）：

- 任务计划程序：开机运行 `python server.py --port 8000`（起始目录 `...\main\server`）
- 或 `server\start.bat` 放进启动文件夹（`shell:startup`）

## 7. 排错对照表

| 现象 | 原因 | 处理 |
|---|---|---|
| 访问 502 | 本机服务没起 / 写成了 `localhost` | 先 `curl 127.0.0.1:8000/api/v1/health`；配置改 `127.0.0.1` |
| 访问 530 | 隧道没连上 Cloudflare | 看 `cloudflared` 日志；加 `--protocol http2` |
| `failed to dial with quic` | UDP 7844 被阻断 | 配置里 `protocol: http2` |
| 域名打不开但隧道日志正常 | DNS 还没生效 / CNAME 没绑上 | `cloudflared tunnel route dns` 重跑；等几分钟 |
| `tunnel login` 打不开浏览器 | 无桌面环境 | 复制它打印的 URL 手动打开；或 `--no-browser` 拿到 URL |
| 重启后地址还在但 502 | 服务没自启 | 装 `cloudflared service install` + 服务自启 |

## 8. 安全提醒（不要跳过）

- `cert.pem`、`<TUNNEL_ID>.json` 是账号级凭据，**不要提交到仓库**（`.gitignore` 已忽略 `*.json`? 没有——请手动别 add）。
- 上公网前**改掉默认令牌**（`app-elder-001` / `fam-demo-2026` / `comm-demo-2026`）和配对码 `8823`，
  否则任何人都能登进来看老人数据。
- 本服务没有 TLS 证书，但经过 Cloudflare 后是 HTTPS，浏览器不会报不安全。
