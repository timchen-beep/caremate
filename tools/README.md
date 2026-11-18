<!-- 作用：tools/ 下每个脚本干什么、什么时候跑、失败怎么读；改完代码一律先 verify_all 再 publish -->
# 工具（tools/）

所有脚本都只用标准库，在仓库根目录跑。改完代码的固定顺序是：**先 `verify_all.py`，过了再 `publish.py`**。

## 一次跑完全部检查

```bash
python tools/verify_all.py            # 完整性 → 语法 → 起服务 → 全部套件 → 产物卫生 → 四个页面
python tools/verify_all.py --flutter  # 另加 flutter analyze（需要 Flutter SDK）
```

退出码 0 = 全过。分支上少套件（例如 `web`/`qt` 没有 MQTT 桥）会打印「本分支没有 test_bridge.py，按 9 套跑」，
文档数字守卫也按实际套数比，不会假报。

## 提交与推送

```bash
python tools/publish.py               # 验证 → 逐文件提交（消息=路径：作用）→ 推当前分支
python tools/publish.py --dry-run     # 只看会提交哪些文件
python tools/publish.py --no-verify   # 已经验过，跳过验证
```

任何一个文件提交失败就**不推送**（否则推上去的是半套改动），退出码 1。

## 分支维护

| 脚本 | 干什么 | 注意 |
|---|---|---|
| `sync_branches.py` | 把 main 的服务端核心（`server.py`/`v1_adapter.py`/`test_v1.py`/四个页面/页面说明）同步到八条分支，每支跑 6/6 + 9/9 再提交推送 | `--dry-run` 先看清单；`--only web` 只做一条；`--with-tools` 顺便更新 `tools/` |
| `merge_from_branches.py` | 反向：在 main 上按归属把 `web`/`qt` 的改动拉回来 | 归档分支是 orphan 历史，**永远不能 `git merge`** |
| `audit_branches.py` | 九条分支静态体检：乱码/BOM/缺作用头/语法错/文档数字漂移/写死令牌/失效链接/代码被截断 | `--branch web` 只看一条；`--json` 出清单；退出码 0 = 干净 |

## 令牌与索引

| 脚本 | 干什么 | 注意 |
|---|---|---|
| `rotate_tokens.py` | 生成新令牌写进 `server/.env`（gitignore），旧文件留 `.bak` | `--easy --length 8` 出好抄的短令牌；只替换四个键，别的键原样保留 |
| `gen_index.py` | 生成 `FILES.md` / `FUNCTIONS.md` | 必须在**仓库根**跑；`git ls-files` 失败就退出，不会把索引清空 |
| `sample_p95.py` | 采样"到点 → 通知"的实际延迟，验 P95 ≤ 30 s | 会自己起临时服务与临时库 |
| `collect_evidence.py` | 跑全部套件，把命令、时间、通过数汇总成一份 markdown 证据（答辩用） | 没服务就自己起临时库；缺套件会明说；任一套失败退出码 1 |
| `push_helper.py` | 推送：代理没开就试直连 | 只在 `publish.py` 里被调用 |

## 读失败

- `verify_all.py` 最后会列出失败项；套件自己也有中文用例名，直接看是哪一条
- 「完整性守卫」失败 = 文件比 `HEAD` 缩水一半以上，多半是脚本用小 buffer 读写截断了（历史事故：39.9 KB 的看板被写成 6.2 KB）
- 「文档数字一致」失败 = 某处还写着旧的「N 套 / M 项」，按提示改成实际值
- 跑验收**不要**带 `--demo`（它把阈值改成 1/3/10 分钟，调度类用例会失败）
