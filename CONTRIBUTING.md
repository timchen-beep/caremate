<!-- 作用：qt 分支开发规约：三条铁律、改完就发（推当前分支）、验证项、Qt 特有的注意点 -->
# 开发规约（qt 分支）

## 一、三条铁律

1. **完整读写**：不要 `read(N)` 截断后回写。
2. **二进制用 `rb`/`wb`**：`encoding=` 文本读写会写坏 PNG/JAR。
3. **改完必须验证**：`python tools/verify_all.py` 全绿。

## 二、改完就发

```bash
python tools/publish.py        # 21 项验证 → 逐文件提交 → 推送**当前分支**
```

`publish.py` 默认推当前分支，所以在 `qt` 分支上跑就推 `qt`，不会误推 `main`。

## 三、验证项（21）

截断守卫 → 二进制魔数 → 语法 → 起服务 → 九套验收 → 产物卫生 → **构建引用一致** → 四个页面 → 文档数字一致。

其中"构建引用一致"对 Qt 分支最关键：它检查 `qt/CMakeLists.txt` 引用的每个 `.cpp/.h/.qml`
是否**存在且已入库**——曾经有四个 `qt/net/*` 文件只存在本地、没进版本库，远端因此编译不过。

## 四、Qt 特有的注意点

1. 新增源文件：加进 `qt/CMakeLists.txt` 的 `qt_add_executable` 列表。
2. 新增 QML：加进 `QML_FILES`，并在 `main.qml` 里能导航到。
3. `LocalStore` 用 SQLite（`Qt6::Sql`），表结构改动要同时改 `load()` 与 `save()`。
4. 端上不自己判 `escalated` / `missed`：那是云端 `scheduler_tick()` 的事，端上只做 `notified`。

## 五、分支

`qt` 是 Qt 路线的唯一迭代分支；`web` 是网页端；`main` 是整合版；`v1-web` / `v2-qt` / `v3-flash` 只读归档。