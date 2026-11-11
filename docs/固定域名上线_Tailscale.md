# 作用：用 Tailscale Funnel 给本机 CareMate 一个固定公网地址（免域名、免服务器），含实测步骤与排错
# 固定公网地址：Tailscale Funnel（免域名）

> 结果：**https://timchen.tail3c910a.ts.net** —— 固定、HTTPS、随时随地可访问，
> 不需要买域名、不需要公网 IP、不需要云服务器。前提是这台电脑开着且联网。

## 一、为什么选它

| 方案 | 固定地址 | 要域名 | 要服务器 | 实测 |
|---|---|---|---|---|
| Cloudflare 快速隧道 | ❌ 每次重启换地址 | 不要 | 不要 | ✅ 能用（HTTP/2） |
| Cloudflare 命名隧道 | ✅ | **要** | 不要 | 未走（缺域名） |
| SSH 隧道（localhost.run / serveo） | ❌ | 不要 | 不要 | ❌ 数据通道 502 |
| **Tailscale Funnel** | ✅ | 不要 | 不要 | ✅ 能用 |

关键差异：Tailscale 用自己账号下的 `*.ts.net` 域名，所以既免费又固定。

## 二、一次性配置（本机已完成，换机器照做）

```powershell
# 1) 安装（winget，不需要管理员下载）
winget install Tailscale.Tailscale

# 2) 登录：会打印一个 https://login.tailscale.com/a/xxxx 链接，浏览器里授权
& "C:\Program Files\Tailscale\tailscale.exe" up

# 3) 在后台开 HTTPS 证书：https://login.tailscale.com/admin/dns → HTTPS Certificates → Enable
#    （不开会报 "your Tailscale account does not support getting TLS certs"）

# 4) 为这个节点开启 Funnel：命令会打印一个 https://login.tailscale.com/f/funnel?node=xxxx 链接
& "C:\Program Files\Tailscale\tailscale.exe" funnel --bg 8000

# 5) 验证证书已签发（可选）
& "C:\Program Files\Tailscale\tailscale.exe" cert timchen.tail3c910a.ts.net
```

本机实际得到的地址：

```
https://timchen.tail3c910a.ts.net          ← 根路径
https://timchen.tail3c910a.ts.net/dashboard
https://timchen.tail3c910a.ts.net/app
https://timchen.tail3c910a.ts.net/kiosk
```

## 三、让它在重启后自动恢复

需要两件事同时满足：

| 组件 | 怎么自启 | 现状 |
|---|---|---|
| Tailscale（含 Funnel 配置） | 安装时装成了 Windows 服务，`Automatic` 启动 | ✅ 已生效 |
| CareMate 后端 | 启动文件夹里的 `CareMate Server.bat` → `server\start-caremate.bat` | ✅ 已放置 |

`server\start-caremate.bat` 用 `pythonw.exe` 静默启动，日志写 `server\server.log`：

```bat
cd /d "%~dp0"
start "" /min "<python 路径>\pythonw.exe" server.py --port 8000 >> "%~dp0server.log" 2>&1
```

手动验证自启脚本（不用重启电脑）：

```powershell
# 停掉当前服务
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" | Where-Object { $_.CommandLine -like '*server.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
# 用 bat 拉起
cmd /c "C:\Users\43915\Documents\GitHub\main\server\start-caremate.bat"
# 健康检查
curl.exe http://127.0.0.1:8000/api/v1/health
```

## 四、排错对照表（都踩过）

| 现象 | 原因 | 处理 |
|---|---|---|
| `cert` 报 `500 ... account does not support getting TLS certs` | 后台没开 HTTPS Certificates | admin/dns → Enable |
| `funnel` 打印 `Funnel is not enabled on your tailnet` | 节点没开 funnel 属性 | 打开它给的 `login.tailscale.com/f/funnel?node=...` 链接点 Enable |
| `cert` 卡住几十秒 | ACME 首次签发慢 | 等 1–2 分钟重试；证书缓存后很快 |
| 公网 502 | 本机服务没起 | `curl 127.0.0.1:8000/api/v1/health`；确认自启 bat 生效 |
| 重启后地址在但 502 | 后端没自启 | 检查启动文件夹里的 bat；`server\server.log` 看报错 |
| 换电脑后地址变 | 节点名换了 | `*.ts.net` 名按机器名生成，可在 admin 里改机器名 |

## 五、安全提醒（上公网前必须做）

1. **改掉默认令牌**：`app-elder-001` / `fam-demo-2026` / `comm-demo-2026` 和配对码 `8823`，
   否则任何人扫到这个域名都能看到老人数据。
2. **换端口或加白名单**：目前 `/dashboard` 任何人都能打开、只是没令牌看不到数据；加密后可留。
3. **别把 `*.ts.net` 地址发到公开群里**，虽然地址算随机，但被扫到仍是暴露面。
4. Tailscale 账号登出/更换设备后 Funnel 会失效，需要重新 `funnel --bg`。

## 六、已知限制

- 免费额度：Funnel 每月 1 GB 流量（演示够用，长期传图片不够）。
- 必须**电脑开着且联网**：关机、休眠、断网都会 502。
- 后端仍是单进程 + SQLite，多人同时访问没问题，但别拿它做生产。
