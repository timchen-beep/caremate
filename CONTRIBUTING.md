<!-- 作用：开发规约：改代码的三条铁律、一键验证怎么跑、提交与分支规范、踩过的坑 -->
# 开发规约（改这个仓库之前先读）

这三条不是建议，是**踩过坑之后定的硬规矩**。

---

## 铁律一：完整读写，绝不"读多少写多少"

任何脚本改文件，都必须**完整读完再完整写回**：

```python
# ✅ 正确
text = open(p, encoding="utf-8").read()          # 读完
open(p, "w", encoding="utf-8", newline="\n").write(text)

# ❌ 错误：只读了 6000 字符，回写时把文件截断
text = open(p, encoding="utf-8").read(6000)
open(p, "w").write(text)
```

**真实事故**：一次批量加注释的脚本用了 `.read(6000)` 后回写，
`server/web/dashboard.html` 从 **39.9 KB 被截断到 6.2 KB**，18 个 JS 函数全丢；
`server/web/app.html`、`server/README.md`、`app/pubspec.lock` 同样被截断。
页面还能返回 200（因为 HTML 结构还在），**只有跑起来点一下才发现按钮全没了**。

判断标准：脚本里出现 `read(N)`、`readline()`、`truncate()`、`fileinput` 时，先停下来想清楚。

**二进制文件必须用 `"rb"` / `"wb"`**，绝不能经过 `encoding=` 的文本读写：

```python
# ✅ 图片/JAR/APK/数据库
raw = open(p, "rb").read()
open(p, "wb").write(raw)

# ❌ 会把 PNG 头 \x89PNG 变成替换字符 efbfbd，文件大小还正常，AAPT 直接失败
text = open(p, encoding="utf-8", errors="replace").read()
open(p, "w").write(text)
```

**真实事故**：一次批量加注释的脚本对目录下所有文件用 `errors="replace"` 读写，把 5 个 `ic_launcher.png`、3 个 PWA 图标和 `gradle-wrapper.jar` 一起写坏——表现为 `AAPT: file failed to compile` 与 `ClassNotFoundException: GradleWrapperMain`，而 `git status` 看不出任何异常。

---

## 铁律二：改完必须验证，而且是"跑起来验证"

只做静态检查不够——截断的 HTML/JS 静态扫描可能不报错。**分级验证**：

| 级别 | 什么时候做 | 命令 |
|---|---|---|
| L1 语法 | 每次改完 | `python -m py_compile`、`bash -n`、`flutter analyze` |
| L2 全量验收 | 每次改后端/页面/测试 | **`python tools/verify_all.py`**（19 项：截断守卫 + 二进制魔数 + 语法 + 服务 + 八套验收 + 产物卫生 + 四个页面 + 文档数字一致） |
| L3 真机 | 交付前 | 见 `docs/验收清单.md` |

一键：

```bash
python tools/verify_all.py            # 八套验收 + 页面检查 + 语法检查
python tools/verify_all.py --flutter  # 额外跑 flutter analyze
```

它会逐项打印 PASS/FAIL，任何一项失败就以非零退出码结束——**CI 用的就是同一套逻辑**。

---

## 铁律三：每个文件的提交信息必须是它自己的说明

GitHub 文件列表的 "Last commit message" 列取的是**最后一次改动该文件的提交**。
批量提交 80 个文件，那一列就会显示 80 条一样的信息，等于没有信息。

规矩：

- 一个文件一次提交，消息格式：`<相对路径>：<这个文件干什么>`
- 例：`server/server.py：CareMate 云端唯一服务：规则展开、实例物化、状态迁移…`
- 新增/大改文件时，头部要有一行 `作用：…`，提交信息直接取它

---

## 提交与分支规范

| 项 | 规矩 |
|---|---|
| 提交信息 | 中文，动词开头（`新增`/`修正`/`移除`），一个提交只做一件事 |
| 分支 `main` | 只放整合后的可运行版本 |
| 分支 `v1-web` / `v2-qt` / `v3-flash` | **归档**，各自独立历史，**永远不要合并进 main** |
| 分支 `*-core` | 只保留实现代码（无文档/APK/测试产物） |
| 归档分支改动 | 用 `git worktree` 单独操作，别在 main 的工作区切分支（会整体替换工作目录） |

---

## 两份索引用生成的，不要手写

| 文件 | 生成方式 |
|---|---|
| `FILES.md` | 扫描每个文件头部的 `作用：` 注释 |
| `FUNCTIONS.md` | 扫描代码里的 `函数 名字：说明` 注释 |

改了代码记得**同步改注释**，否则索引和代码会脱节。

---

## 已经踩过的坑（都别再踩）

| 坑 | 现象 | 正确做法 |
|---|---|---|
| 截断回写 | 大文件变小，页面还在但功能没了 | 完整读写；跑 `verify_all.py` |
| 文本方式读写二进制 | PNG/JAR 头被替换字符覆盖，构建期才报错 | 二进制用 `"rb"`/`"wb"`；`verify_all.py` 已加魔数守卫 |
| 测试产物入库 | `*.db` / `__pycache__` 被 `git add -A` 一起提交（本仓库发生过 3 次） | 跑完测试后 `verify_all.py` 的「产物卫生」会拦；分支必须有 `.gitignore` |
| Windows 控制台 GBK | 中文输出乱码、`UnicodeDecodeError` | 脚本内 `encoding="utf-8", errors="replace"`；输出写文件再读 |
| UTF-8 BOM | Dart 报 `Illegal character '65279'` | 写文件用 `utf-8` 且**不加 BOM** |
| CRLF/LF | git 反复提示"文件已修改"但内容没变 | 仓库统一 LF；`.gitattributes` 里 `*.bat eol=crlf` |
| `.github` 被当成 `.git` | 遍历时整个 CI 目录被跳过 | 判断用 `os.sep + ".git"`，不要用子串匹配 |
| `--demo` 参数 | 跑验收会失败（阈值被改成 1/3/10 分钟） | 验收时**不要**带 `--demo` |
| 测试的时区 | CI 上"时区与历史"失败 | 测试要固定 `TZ=Asia/Shanghai`，或从服务端 `/health` 取时区 |
| 服务多进程 | 提醒发两遍 | 只跑单进程，`deploy/caremate.service` 已这么配 |
| 代理 | `git push` 报 `Recv failure` | git 单独配 `http.https://github.com/.proxy`（浏览器代理它不认） |

---

## 提交前 checklist

```
[ ] 改的文件是完整读写，没有截断
[ ] python tools/verify_all.py 全绿
[ ] 改了 .dart 就跑 flutter analyze（--flutter）
[ ] 新文件头有「作用：」，新函数上方有「函数 X：」
[ ] FILES.md / FUNCTIONS.md 已重新生成
[ ] 提交信息按文件各自写，不是一条批量说明
```