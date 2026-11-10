# -*- coding: utf-8 -*-
"""生成 FILES.md（每个文件一行作用）与 FUNCTIONS.md（每个函数一行说明）。"""
import io, os, re, subprocess, sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
DESC_PAT = re.compile(r"作用[：:]\s*(.+?)\s*(?:-->|--)?\s*$", re.M)
FUNC_PAT = re.compile(r"^\s*(?:#|//)\s*函数\s*([A-Za-z_][\w:]*)\s*[：:]\s*(.+?)\s*$", re.M)
SKIP_EXT = {".png", ".jpg", ".jpeg", ".jar", ".apk", ".ico", ".db", ".zip", ".docx", ".keystore"}
# 少数文件不能写注释（JSON 系）或本身就有固定含义，这里给固定说明
FIXED_DESC = {
    "LICENSE": "开源许可：MIT（作业演示用，引用第三方库见 third_party 许可）",
    "server/web/manifest.webmanifest": "PWA 清单：应用名、图标、显示模式（装到桌面像原生 App）",
    "integration/yiban_client/对接后端.patch": "给颐伴手机端仓库的补丁（git am 可用）：真 HTTP 传输 + 同步引擎 + 端上灌入入口",
}

def tracked():
    out = subprocess.run(["git", "-C", ROOT, "-c", "core.quotepath=false", "ls-files"],
                         capture_output=True, text=True, encoding="utf-8").stdout
    return [p for p in out.splitlines() if p]

files_rows, func_rows = [], []
for rel in tracked():
    p = os.path.join(ROOT, rel.replace("/", os.sep))
    if not os.path.isfile(p):
        continue
    ext = os.path.splitext(rel)[1].lower()
    desc = ""
    if ext not in SKIP_EXT:
        try:
            head = io.open(p, encoding="utf-8", errors="replace").read(4000)
        except OSError:
            head = ""
        m = DESC_PAT.search(head)
        desc = m.group(1).strip() if m else "未标注"
        if ext in (".py", ".dart", ".cpp", ".h", ".qml", ".sh"):
            for fm in FUNC_PAT.finditer(io.open(p, encoding="utf-8", errors="replace").read()):
                func_rows.append((rel, fm.group(1), fm.group(2).strip()[:90]))
    else:
        desc = "二进制资源"
    if rel in FIXED_DESC:
        desc = FIXED_DESC[rel]
    if desc == "未标注" and ext == ".md":
        first = head.split("\n", 1)[0].lstrip("# ").strip()
        if first and "作用" not in first:
            desc = first[:60]
    files_rows.append((rel, desc))

files_rows.sort()
func_rows.sort()

lines = ["<!-- 作用：文件索引：每个文件一行说明（由 tools/gen_index.py 生成，勿手改） -->",
         "# 文件索引（%d 个）" % len(files_rows), "",
         "| 文件 | 作用 |", "|---|---|"]
for rel, desc in files_rows:
    lines.append("| `%s` | %s |" % (rel, desc.replace("|", "\\|")))
io.open(os.path.join(ROOT, "FILES.md"), "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")

lines = ["<!-- 作用：函数索引：每个函数一行说明（由代码里的「函数 xxx：…」注释生成，勿手改） -->",
         "# 函数索引（%d 个）" % len(func_rows), "",
         "| 文件 | 函数 | 说明 |", "|---|---|---|"]
for rel, name, desc in func_rows:
    lines.append("| `%s` | `%s` | %s |" % (rel, name, desc.replace("|", "\\|")))
io.open(os.path.join(ROOT, "FUNCTIONS.md"), "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")

unmarked = [r for r, d in files_rows if d == "未标注"]
print("FILES.md 收录 %d 个文件；FUNCTIONS.md 收录 %d 个函数；未标注 %d" % (len(files_rows), len(func_rows), len(unmarked)))
for u in unmarked[:10]:
    print("   未标注:", u)