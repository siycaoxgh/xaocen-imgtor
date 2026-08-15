# XAOCEN ImgTor 安装包

v5.3.2 的 Inno Setup 配置位于 `installer/XAOCEN-ImgTor-v5.3.2.iss`。

先构建 `dist/XAOCEN-ImgTor-v5.3.2.exe`，再使用 Inno Setup 6 编译：

```bat
ISCC.exe installer\XAOCEN-ImgTor-v5.3.2.iss
```

安装程序、桌面快捷方式、开始菜单快捷方式和卸载程序统一使用项目内的 `resources/xaocen-imgtor.ico`。
