# XAOCEN ImgTor

**晓枨图像工具** · 轻量 · 高效 · 专注于图像效率

XAOCEN ImgTor 是一款面向 Windows 的轻量级图像效率工具，用于快速截图、动态图像录制、图片浏览、裁剪处理以及多格式导出。

## 功能

- 快速截图：全局快捷键、自由大小、固定比例、固定尺寸、PNG/JPG/BMP、自动保存与剪贴板。
- 动图录制：GIF、APNG、Animated WebP，支持 FPS、比例、固定尺寸、倒计时和最长 15 秒录制。
- 视频录制：通过独立 FFmpeg 插件录制 MP4，不增加核心程序的 FFmpeg 依赖。
- 图片浏览：缩略图网格、GIF/视频/Motion 图识别、预览、打开、删除和分类筛选。
- 图片裁剪：自由绘制、固定比例、固定尺寸、动画格式裁剪和覆盖/另存。
- Motion Photo：支持 Google 通用配置和小米兼容实验性配置，可选择 MP4 片段后合成。
- 设置与插件：快捷键映射、主题、语言、保存目录和可信插件安装管理。

## 运行方式

### 源码运行

Windows 需要 Python 3.10+、Tkinter，以及 `requirements.txt` 中列出的依赖：

```bat
python -m pip install -r requirements.txt
启动.bat
```

### 免安装发行版

运行 `release/XAOCEN-ImgTor-v5.3.2.exe`，或解压 `release/XAOCEN-ImgTor-v5.3.2-portable.zip` 后直接运行。

发布包不包含用户配置、插件和 FFmpeg；这些内容保存在用户目录中，避免单文件 EXE 临时目录被写入。

## 可选插件

插件仓库：[xaocen-plugin](https://github.com/siycaoxgh/xaocen-plugin)

可选插件包括：

- `android_motion_photo.xaocen-plugin`：Android Motion Photo 合成、检查和提取。
- `video_recorder_ffmpeg.xaocen-plugin`：FFmpeg MP4 录制、视频探测、缩略图和片段裁剪。

在设置页选择插件目录，或将 `.xaocen-plugin` 文件复制到插件目录后刷新。程序会校验包内 SHA-256 并自动解包。插件属于可信代码机制，请只安装可信来源的插件。

## 项目文档

- [更新日志](CHANGELOG.md)：记录版本、功能、修复和已知限制。
- [平台支持说明](docs/PLATFORM_SUPPORT.md)：Windows、macOS 和 Linux 的支持范围。
- [插件分发说明](docs/PLUGIN_PACKAGES.md)：`.xaocen-plugin` 格式和完整性校验。
- [FFmpeg 安装说明](docs/FFMPEG_SETUP.md)：视频插件的外部 FFmpeg 配置。
- [启动与资源说明](docs/STARTUP_AND_RESOURCES.md)：开机自启动、发布包体积和内存占用边界。
- [Apache-2.0 许可证](LICENSE)
- [归档仓库](https://github.com/siycaoxgh/xaocen-imgtor-archive)：旧版入口、旧 Tk 界面和测试历史。

## 测试与构建

当前核心自动化测试覆盖配置迁移、原子保存、快捷键、尺寸解析、比例计算、动图输出、录制帧数、裁剪坐标、图库 API、插件和 Motion Photo 等功能。

```bat
python -m unittest discover -s tests -q
node --check ui/app.js
```

PyInstaller 构建配置位于 `XAOCEN-ImgTor.spec`。核心程序与媒体插件分离，以控制安装体积和常驻内存；FFmpeg 仅在视频功能使用时由插件调用。设置页可选“开机自启动”，登录 Windows 后自动启动截图监听。

## 品牌与版权

产品：**XAOCEN ImgTor**  
中文：**晓枨图像工具**  
开发：**XAOCEN STUDIO**  
版权：**© 2026 XAOCEN. All Rights Reserved.**

项目仓库：[siycaoxgh/xaocen-imgtor](https://github.com/siycaoxgh/xaocen-imgtor)

本项目以 [Apache License 2.0](LICENSE) 发布。第三方依赖和插件仍受其各自许可证约束。
