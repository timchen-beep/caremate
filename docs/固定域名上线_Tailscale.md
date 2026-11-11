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

## 三、关机再开机之后（已配置好，实测过）

| 组件 | 谁负责启动 | 状态 |
|---|---|---|
| Tailscale（含 Funnel 配置） | 安装时注册的 Windows 服务 `Tailscale`（Automatic） | ✅ Running |
| CareMate 后端 | 启动文件夹里的 `CareMate Server.vbs` → `server\start-caremate.vbs` | ✅ 已配置 |

重启后发生的事，按顺序：

1. Windows 启动 → `Tailscale` 服务自动起来，**Funnel 配置保存在 tailscaled 状态里**，不需要重新 `funnel --bg`
2. 你**登录 Windows** → 启动文件夹里的 VBS 静默拉起后端（`pythonw`，不弹窗）
3. 后端启动时自己读 `server\.env`（令牌/配对码），所以轮换过的令牌重启后依然有效
4. `https://timchen.tail3c910a.ts.net` 恢复可用（通常 10–20 秒内）

**注意**：启动文件夹是在**用户登录后**才执行。所以脚本必须进桌面一次——如果开机停在登录界面不登录，地址会 502。

### 开机后一分钟自检（照做）

```powershell
# 1) 服务在不在
Get-Service Tailscale | Select-Object Status,StartType
# 2) Funnel 还在不在
& "C:\Program Files\Tailscale\tailscale.exe" funnel status
# 3) 后端在不在
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" | Where-Object { $_.CommandLine -like '*server.py*' }
# 4) 本地通不通
curl.exe http://127.0.0.1:8000/api/v1/health
# 5) 公网通不通
curl.exe https://timchen.tail3c910a.ts.net/api/v1/health
```

任何一步失败：

| 卡在哪 | 手动修 | 说明 |
|---|---|---|
| 2) Funnel 没了 | `& "C:\Program Files\Tailscale\tailscale.exe" funnel --bg 8000` | 极少见，换账号/重装后会出现 |
| 3) 后端没起 | 双击 `server\start-caremate.vbs` | 或查 `server\server.log` |
| 4) 本地通、公网 502 | 等 15 秒再试 | Tailscale 重连边缘需要几秒 |
| 全都正常但公网还是 502 | `& "C:\Program Files\Tailscale\tailscale.exe" status` 看是否掉线 | 重新登录 `tailscale up` |

### 为什么用 VBS 而不是 .bat

实测在这台机器上，`.bat` 里 `start "" /min "pythonw.exe" ...` 会**卡住不返回**（cmd 的 start 在某些环境阻塞），
导致启动事项挂死、服务起不来。VBS 用 `WScript.Shell.Run(..., 0, False)` 启动即返回，实测 0.01 秒。

## 四、排错对照表（都踩过）

| 现象 | 原因 | 处理 |
|---|---|---|
| `cert` 报 `500 ... account does not support getting TLS certs` | 后台没开 HTTPS Certificates | admin/dns → Enable |
| `funnel` 打印 `Funnel is not enabled on your tailnet` | 节点没开 funnel 属性 | 打开它给的 `login.tailscale.com/f/funnel?node=...` 链接点 Enable |
| `cert` 卡住几十秒 | ACME 首次签发慢 | 等 1–2 分钟重试；证书缓存后很快 |
| 公网 502 | 本机服务没起 | `curl 127.0.0.1:8000/api/v1/health`；确认自启 bat 生效 |
| 重启后地址在但 502 | 后端没自启 | 检查启动文件夹里的 bat；`server\server.log` 看报错 |
| 换电脑后地址变 | 节点名换了 | `*.ts.net` 名按机器名生成，可在 admin 里改机器名 |

## 五、令牌轮换（已做，且可随时重做）

代码里的 `app-elder-001` / `fam-demo-2026` / `comm-demo-2026` / 配对码 `8823` 只是**演示值**。
上公网前执行一次（会生成随机值并写入 `server/.env`，该文件已被 `.gitignore` 忽略）：

```bash
python tools/rotate_tokens.py          # 生成
python tools/rotate_tokens.py --print  # 查看当前值
```

`server\start-caremate.bat` 启动时会读取 `server/.env`，所以轮换后只要重启服务：

```powershell
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" | ForEach-Object { if ($_.CommandLine -like '*server.py*') { Stop-Process -Id $_.ProcessId -Force } }
cmd /c "C:\Users\43915\Documents\GitHub\main\server\start-caremate.bat"
```

验证（旧令牌必须被拒）：

```bash
curl.exe -H "X-Token: <新家属令牌>" https://<你的地址>/api/v1/overview   # 200
curl.exe -H "X-Token: fam-demo-2026"    https://<你的地址>/api/v1/overview   # 401
```

另外两条仍然成立：

1. **别把令牌和地址发到公开群里**：`app-elder-001` / `fam-demo-2026` / `comm-demo-2026` 和配对码 `8823`，
   否则任何人扫到这个域名都能看到老人数据。
2. **换端口或加白名单**：目前 `/dashboard` 任何人都能打开、只是没令牌看不到数据；加密后可留。
3. **别把 `*.ts.net` 地址发到公开群里**，虽然地址算随机，但被扫到仍是暴露面。
4. Tailscale 账号登出/更换设备后 Funnel 会失效，需要重新 `funnel --bg`。

## 六、已知限制

- 免费额度：Funnel 每月 1 GB 流量（演示够用，长期传图片不够）。
- 必须**电脑开着且联网**：关机、休眠、断网都会 502。
- 后端仍是单进程 + SQLite，多人同时访问没问题，但别拿它做生产。
