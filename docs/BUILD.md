# v5 构建说明

PyInstaller 是构建依赖，不属于核心运行时。构建机使用项目 Python 执行：

```bat
python -m pip install -r requirements.txt -r requirements-build.txt
pyinstaller --clean --noconfirm XAOCEN-ImgTor.spec
```

输出文件名包含版本号，例如 `dist/XAOCEN-ImgTor-v5.0.0.exe`。构建前请完全退出旧版程序、托盘和后台 worker；如果旧 EXE 仍被占用，Windows 会在最后一步返回 `WinError 5`。

构建前应通过：

```bat
python -m unittest discover -s tests -q
node --check ui/app.js
```

输出的 EXE 需要在 Windows 实机验证截图快捷键、动图 worker、视频插件、托盘和单实例锁。最终用户不需要安装 PyInstaller。
