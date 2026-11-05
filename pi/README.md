# 树莓派 / 香橙派部署（E3 路线）

把后端与 MQTT broker 放到一台 ARM 小板上，手机与传感器都走局域网。

## 文件

| 文件 | 作用 |
|---|---|
| `mosquitto.conf` | broker 配置（局域网监听） |
| `caremate-server.service` | systemd：单进程跑后端 |
| `caremate-bridge.service` | systemd：把 outbox 发到 broker |
| `bridge.py` | 零依赖 MQTT 3.1.1 客户端（CONNECT / PUBLISH / PINGREQ） |
| `setup-pi.sh` | 一键安装（apt + mosquitto + systemd） |

## 用法

```bash
sudo bash pi/setup-pi.sh
mosquitto_sub -h 127.0.0.1 -t 'home/#' -v     # 另开窗口盯着
```

后端代码在 `../server/`，部署时拷到 `/opt/caremate`。

## 已知限制

`bridge.py` 只做过报文级自测（CONNECT/PUBLISH 编码正确），**未连真实 broker 验证**。