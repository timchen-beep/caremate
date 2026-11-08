<!-- 作用：推送到 GitHub 的 3 条命令、常见报错与仓库内容边界 -->
# 推到 GitHub（3 条命令）

本目录已经是**初始化好并完成首次提交**的 git 仓库（92 个文件，约 0.5 MB，无数据库、无私钥）。

## 1. 在 GitHub 建一个空仓库

网页上 New repository → 名字随意（如 `caremate`）→ **不要**勾选 "Add a README / .gitignore / license"（否则会有冲突）→ Create。

## 2. 关联并推送

```bat
cd <这个目录>
git remote add origin https://github.com/timchen-beep/caremate.git
git branch -M main
git push -u origin main
```

推送时 Git Credential Manager 会弹窗（浏览器授权或输入 PAT），**权限在你手里**。

## 3. 校验

打开仓库页面，应看到：`README.md`、`server/`、`app/`、`docs/`、`scripts/`、`device/`、`magisk-module/`、`LICENSE`。

## 常见问题

| 现象 | 处理 |
|---|---|
| `remote origin already exists` | `git remote set-url origin <url>` |
| `src refspec main does not match any` | 先 `git checkout -b main` 再 push |
| 提示文件太大 | 本仓库已排除 APK/数据库；若仍报错，检查是否把 `build/` 加进来了 |
| 中文文件名显示为转义 | 执行 `git config core.quotepath false` |
| 想换提交信息 | `git commit --amend -m "新信息"` 后 `git push -f`（仅首次推送前） |

## 仓库里**没有**的东西（有意排除）

- `*.db` / `*.db-wal` / `*.db-shm`：运行时会生成，含演示数据
- `*.jks` / `key.properties`：签名私钥，**绝不能入库**
- `app/build/`、`.dart_tool/`：构建产物
- `*.apk`：产物请在 GitHub Releases 里发，不进 git 历史

需要私有化时把仓库设为 Private；但注意课程提交通常要求公开可访问。

