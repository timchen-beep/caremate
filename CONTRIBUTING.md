<!-- 作用：开发规约：三条铁律、改完就发、迭代分支与 main 合并、提交与分支规范、踩过的坑 -->
# 开发规约（改这个仓库之前先读）

这几条不是建议，是**踩过坑之后定的硬规矩**。

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

**真实事故**：一次批量加注释的脚本对所有文件用 `errors="replace"` 读写，把 5 个 `ic_launcher.png`、
3 个 PWA 图标和 `gradle-wrapper.jar` 一起写坏——表现为 `AAPT: file failed to compile` 与
`ClassNotFoundException: GradleWrapperMain`，而 `git status` 看不出任何异常。

---

## 铁律二：改完必须验证，而且是"跑起来验证"

只做静态检查不够——截断的 HTML/JS 静态扫描可能不报错。**分级验证**：

| 级别 | 什么时候做 | 命令 |
|---|---|---|
| L1 语法 | 每次改完 | `python -m py_compile`、`bash -n`、`flutter analyze` |
| L2 全量验收 | 每次改后端/页面/测试 | **`python tools/verify_all.py`**（21 项：截断守卫 + 二进制魔数 + 语法 + 服务 + 九套验收 + 产物卫生 + 构建引用一致 + 四个页面 + 文档数字一致） |
| L3 真机 | 交付前 | 见 `docs/验收清单.md` |

```bash
python tools/verify_all.py            # 21 项
python tools/verify_all.py --flutter  # 额外跑 flutter analyze
```

逐项打印 PASS/FAIL，任何一项失败就以非零退出码结束——**CI 用的就是同一套逻辑**。

---

## 铁律三：每个文件的提交信息必须是它自己的说明

GitHub 文件列表的 "Last commit message" 列取的是**最后一次改动该文件的提交**。
批量提交 80 个文件，那一列就会显示 80 条一样的信息，等于没有信息。

规矩：

- 一个文件一次提交，消息格式：`<相对路径>：<这个文件干什么>`
- 例：`server/server.py：CareMate 云端唯一服务：规则展开、实例物化、状态迁移…`
- 新增/大改文件时，头部要有一行 `作用：…`，提交信息直接取它

---

## 改完就发（固定流程）

任何改动完成后，**只跑一条命令**：

```bash
python tools/publish.py              # 验证 21 项 → 逐文件提交 → 推送**当前分支**
python tools/publish.py --dry-run    # 只看会提交什么
```

规矩：

- **验证不过不提交**：脚本直接退出，一个文件都不动
- **推的是当前分支**：在 `web` 上跑就推 `web`，不会误推 `main`
- **目录会被展开**：`?? qt/net/` 这种目录会逐个文件提交（曾因只处理 `isfile` 漏掉四个文件）

---

## 迭代分支与 main 合并（方案 2）

改动的**落点是两个迭代分支**，`main` 只做整合：

| 改什么 | 在哪个分支改 | 怎么发 |
|---|---|---|
| 网页端（后端、看板、PWA） | `web` | `git checkout web` → 改 → `python tools/publish.py` |
| Qt 老人端（`qt/`、对接补丁） | `qt` | `git checkout qt` → 改 → `python tools/publish.py` |
| 工具与整合文档 | `main` | `git checkout main` → 改 → `python tools/publish.py` |

**定期把两个分支的成果合回 main**（回 `main` 执行）：

```bash
git checkout main
python tools/merge_from_branches.py --dry-run   # 先看会拉哪些文件
python tools/merge_from_branches.py             # 拉取 → 验证 → 逐文件提交 → 推 main
```

归属规则（写死在 `tools/merge_from_branches.py` 里）：

| 分支 | 归属 |
|---|---|
| `web` | `server/` 整目录 + **双方都有的** `docs/` 文件 |
| `qt` | `qt/`、`integration/` 整目录 + **双方都有的** `docs/` 文件 |
| `main` | `tools/`、根目录文档、`app/`、硬件相关目录 |

### 改完后端之后：把 `server/` 推到另一条迭代分支

后端代码在 `web` 分支迭代，但 `qt` 分支也连同一个后端（`server/` 各有一份）。所以：
**在 `web` 上改完后端，要顺手把它同步进 `qt`**（反过来也一样）：

```bash
python tools/sync_branches.py --only qt          # main → qt：覆盖 server/ 核心（+已有文档），验证后提交推送
python tools/sync_branches.py --only web         # main → web：网页端分支同理
python tools/sync_branches.py --only qt --dry-run   # 只看会覆盖哪些文件
```

它做四件事，顺序固定：

1. 差异核对（覆盖前先看 `git status`，没变化直接"已是最新"）
2. 覆盖 `server.py` / `v1_adapter.py` / `test_v1.py`（外加分支里已有的对接文档）
3. **起服务验证**：`test_accept` 6 项 + `test_v1` 9 项（`test_accept` 不会自己起服务，工具会先启动）
4. 逐文件提交 → 推送该分支

> 工具默认只同步"服务端核心"这几个文件；`tools/` 归 main，不加 `--with-tools` 就不会动它。
> 归档分支（`v1-web`/`v2-qt`/`v3-flash*`）也可以用同一命令，省略 `--only` 就是全部六条一起同步。

两个关键约束：

1. **不要用 `git merge`**：`web`/`qt` 是 orphan 分支（与 main 无共同历史），整枝合并会把分支独有文件当新增、产生大量伪冲突。
2. **不要按目录 `git checkout` main 独有的目录**：`git checkout <branch> -- <dir>` 会**删除** main 上该目录里分支没有的文件。工具只对"分支也全有"的目录这么做，文档则逐个文件挑"双方都有"的。

---

## 提交与分支规范

| 项 | 规矩 |
|---|---|
| 提交信息 | 中文，动词开头（`新增`/`修正`/`移除`），一个提交只做一件事 |
| 分支 `main` | 整合版：网页端 + Qt 骨架 + Flutter 验证版 + 硬件；由迭代分支合并而来 |
| 分支 `web` | **网页端唯一迭代分支**（只有后端 + 三个网页 + PWA + 九套验收） |
| 分支 `qt` | **Qt 老人端唯一迭代分支**（`qt/` + 后端 + 对接补丁） |
| 分支 `v1-web` / `v2-qt` / `v3-flash` | **归档**，独立历史，**永远不要合并进 main** |
| 分支 `*-core` | 只保留实现代码（无文档/APK/测试产物） |
| 任何分支改动 | 用 `git worktree` 单独操作，别在 main 的工作区切分支（会整体替换工作目录） |

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
| 测试产物入库 | `*.db` / `__pycache__` / `acceptance.json` 被一起提交（发生过多次） | 「产物卫生」守卫会拦；分支必须有 `.gitignore` |
| 目录级 `git checkout` | main 上分支没有的文件被删掉 | 只对"分支也全有"的目录用；文档逐个挑共有文件 |
| orphan 分支用 merge | 大量伪冲突、分支独有文件被当新增 | 用 `merge_from_branches.py` 按归属拉取 |
| 提交脚本只处理 `isfile` | `?? qt/net/` 目录被跳过，远端缺文件 | 用 `git add -A` 再逐个提交；「构建引用一致」守卫会拦 |
| 脚本里"假成功" | 锚点没匹配也打印"已更新" | 替换后断言原文消失/新文出现 |
| Windows 控制台 GBK | 中文输出乱码、`UnicodeDecodeError` | 脚本内 `encoding="utf-8", errors="replace"`；输出写文件再读 |
| UTF-8 BOM | Dart 报 `Illegal character '65279'` | 写文件用 `utf-8` 且**不加 BOM** |
| `.github` 被当成 `.git` | 遍历时整个 CI 目录被跳过 | 判断用 `os.sep + ".git"`，不要用子串匹配 |
| `--demo` 参数 | 跑验收会失败（阈值被改成 1/3/10 分钟） | 验收时**不要**带 `--demo` |
| 测试的时区 | CI 上"时区与历史"失败 | 测试固定 `TZ=Asia/Shanghai` |
| 服务多进程 | 提醒发两遍 | 只跑单进程，`deploy/caremate.service` 已这么配 |
| 代理 | `git push` 报 `Recv failure` | git 单独配 `http.https://github.com/.proxy` |

---

## 提交前 checklist

```
[ ] 改的文件是完整读写，没有截断
[ ] python tools/verify_all.py 全绿（21 项）
[ ] 改了 .dart 就跑 flutter analyze（--flutter）
[ ] 新文件头有「作用：」，新函数上方有「函数 X：」
[ ] FILES.md / FUNCTIONS.md 已重新生成
[ ] 在正确的分支上（web / qt / main），提交信息按文件各自写
```
