<!-- 作用：服务端页面的说明：三个页面各给谁用、各自的关键函数 -->
# 服务端页面

| 文件 | 给谁用 | 关键函数 |
|---|---|---|
| `dashboard.html` | 家属（电脑浏览器） | `refresh()` 每 5 秒刷新、`watchAlarms()` 长轮询、`incoming()` 弹红条 |
| `app.html` | 老人（网页/PWA 预览版） | `act()` 提交动作、`speak()` 语音、`runCheck()` 无障碍自检 |
| `kiosk.html` | 老人（专注模式全屏） | `tick()` 刷新、`fire()` 呼救/退出 |
| `index.html` | 所有人 | 落地页与三个入口 |
| `sw.js` | 浏览器 | Service Worker：缓存静态页，离线可打开 |

这些页面**不含业务逻辑**：只负责显示与把点击转成一次接口调用。状态全在 `server.py`。