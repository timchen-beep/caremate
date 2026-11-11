' 作用：静默启动 CareMate 后端（开机/登录时由启动文件夹调用；不弹窗、不依赖 cmd start）
Option Explicit
Dim sh, fso, here
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
here = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = here
sh.Run """" & "C:\Users\43915\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\pythonw.exe" & """ server.py --port 8000", 0, False