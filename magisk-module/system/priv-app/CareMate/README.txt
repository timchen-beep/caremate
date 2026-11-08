作用：说明：把 app/CareMate-release.apk 复制到本目录并命名为 CareMate.apk

把 app/CareMate-release.apk 复制到本目录，文件名保持 CareMate.apk：

  copy app\CareMate-release.apk magisk-module\system\priv-app\CareMate\CareMate.apk

打包成 zip 时，压缩包根目录要直接是 module.prop（不要多一层文件夹）：
  cd magisk-module && 7z a ..\CareMate-Kiosk-v1.zip *

