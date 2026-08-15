# XAOCEN ImgTor 项目归档说明

## 项目基本信息

- 产品名：XAOCEN ImgTor
- 中文名：晓枨图像工具
- 当前版本：v5.3.2
- 开发方：XAOCEN STUDIO
- 版权：© 2026 XAOCEN. All Rights Reserved.
- 项目标语：轻量 · 高效 · 专注于图像效率
- 归档日期：2026-08-15

XAOCEN ImgTor 是面向 Windows 的轻量级图像效率工具，支持快速截图、动态图像录制、视频录制、图片浏览、图片裁剪以及 Motion Photo 导出。

## 仓库分工

- 主程序仓库：<https://github.com/siycaoxgh/xaocen-imgtor>
  - 核心程序、HTML UI、测试、构建配置和项目文档。
- 插件仓库：<https://github.com/siycaoxgh/xaocen-plugin>
  - 视频录制插件、Android Motion Photo 插件、插件包和 SDK 说明。
- 历史归档仓库：<https://github.com/siycaoxgh/xaocen-imgtor-archive>
  - 旧版入口、旧 Tk 界面、迁移备份、测试记录和历史构建资料。

发布目录 `release/` 不作为源码仓库内容上传。EXE、Portable ZIP 和安装包由维护者单独上传到 GitHub Releases。

## 当前目录结构

```text
xaocen-imgtor/
├── docs/                    项目、构建、平台和插件文档
├── plugin_examples/         插件示例源码
├── plugin_sdk/              插件开发说明
├── src/xaocen_imgtor/       主程序 Python 包
├── tests/                   自动化测试
├── tools/                   构建和插件工具
├── ui/                      HTML/CSS/JavaScript 界面
├── archive/                 本地历史归档，不参与运行
├── release/                 本地发布包，不参与源码上传
├── webapp.py                主启动入口
├── XAOCEN-ImgTor.spec       PyInstaller 配置
└── 启动.bat                 Windows 启动脚本
```

## 构建方式

### 源码运行

在项目根目录执行：

```bat
python -m pip install -r requirements.txt
python webapp.py
```

也可以双击 `启动.bat`。

### 自动化测试

```bat
python -m unittest discover -s tests -q
node --check ui/app.js
```

### PyInstaller 构建

```bat
python -m pip install -r requirements-build.txt
pyinstaller --clean --noconfirm XAOCEN-ImgTor.spec
```

构建产物位于 `dist/`。正式发布前应将 EXE、Portable ZIP 和插件包复制到带版本号的 `release/` 子目录，并进行独立启动测试。

## 插件安装方式

插件目录默认位于：

```text
%LOCALAPPDATA%\drawru-imgtor\plugins
```

程序启动或在设置页刷新插件时，会自动创建不存在的插件目录。也可以在设置页选择自定义目录。

安装方式：

1. 从插件仓库下载 `.xaocen-plugin` 文件；
2. 将文件放入插件目录；
3. 在软件设置页点击“检查插件”或重新启动软件；
4. 程序校验包内清单与 SHA-256 后自动解包；
5. 安装后的运行目录是插件文件夹，`.xaocen-plugin` 是用于分发的压缩包。

当前插件包括：

- `android_motion_photo.xaocen-plugin`：Android Motion Photo 合成、检查和提取；
- `video_recorder_ffmpeg.xaocen-plugin`：MP4 视频录制、视频检测、缩略图和片段裁剪。

插件属于可信代码机制，不是安全沙箱。只安装来自可信来源、能够确认 SHA-256 或官方发布记录的插件。

## FFmpeg 配置方式

视频录制插件需要单独准备 FFmpeg，不随核心程序常驻打包，以控制程序体积。

1. 从 FFmpeg 官方或可信构建来源下载 Windows 版本；
2. 解压得到 `ffmpeg.exe`；
3. 将它放入视频插件目录，或在设置页选择插件目录；
4. 点击“检查插件”确认 FFmpeg 可用；
5. 只有使用视频录制、视频预览或 Motion Photo 片段裁剪时才会调用 FFmpeg。

具体目录和版本要求见 [FFmpeg 配置说明](FFMPEG_SETUP.md)。

## 已完成内容

- HTML/CSS/JavaScript + pywebview 主界面；
- 快速截图、比例约束、固定尺寸、格式选择、自动保存和剪贴板；
- GIF、APNG、Animated WebP 动图录制；
- FFmpeg 插件视频录制；
- 图片浏览、缩略图、动画预览和分类筛选；
- 图片裁剪、固定比例、固定尺寸和动画输出；
- 圆角处理：整图 Alpha 圆角蒙版、0–50% 短边比例、PNG/WebP 原尺寸导出；
- Android Motion Photo 通用与小米兼容实验性导出；
- 插件目录管理、插件包校验和 SHA-256 校验；
- 系统托盘、单实例、配置迁移和原子配置保存；
- Windows 当前用户开机自启动设置；
- 中英双语、亮色/暗色主题和统一 UI 设计系统；
- PyInstaller Windows 单文件构建流程。

## 已知限制

- 当前产品以 Windows 为主要支持平台；macOS/Linux 分支尚未完成实机回归；
- 多显示器、混合 DPI、负坐标屏幕仍需要更多设备测试；
- Motion Photo 是图片与视频的封装，不同厂商相册对元数据支持并不一致；
- 小米相册、部分社交平台可能要求特定元数据、命名或视频时长；
- Apple Live Photo 尚未作为 Windows 核心功能承诺；
- FFmpeg 由插件调用，缺失或编码器不兼容时无法录制视频；
- 插件可以以当前用户权限读写文件和启动进程，不能视为安全隔离环境；
- 大尺寸图片和视频预览可能造成额外内存占用。

## 下一步开发计划

1. 完善 FFmpeg 检测、安装引导和视频编码错误提示；
2. 增加 Motion Photo 视频片段更直观的预览和时间轴选择；
3. 继续收集小米、其他 Android 厂商和不同社交平台的兼容性测试数据；
4. 评估 Android Motion Photo 与 Apple Live Photo 的实验性转换插件；
5. 补充多显示器、混合 DPI 和不同 Windows 缩放比例的回归测试；
6. 完善插件签名/哈希发布清单和官方插件下载说明；
7. 根据实际用户反馈优化大文件预览、缩略图缓存和启动速度。

## 本次 Codex 开发过程摘要

本项目经历了从 Tkinter 多入口 UI 到 HTML/CSS/JavaScript + pywebview 主界面的迁移，随后完成了配置中心、快捷键、截图/录制浮层、图片浏览、裁剪、托盘、插件机制和 PyInstaller 构建的多轮修复与统一。

本轮最终整理内容包括：

- v5.0 架构迁移到 `src/xaocen_imgtor/`；
- 旧入口和旧 Tk 界面迁移至本地 `archive/`；
- 插件源码与插件包拆分到独立仓库；
- 主程序、插件和历史资料分别推送到三个 GitHub 仓库；
- 主仓库根目录清理为只保留 `webapp.py` 等必要入口文件；
- v5.0.1 构建、测试和发布目录整理完成；v5.1.0 新增圆角处理模式；v5.2.0 修复矩形裁剪模式回归并新增多尺寸 ICO 导出；v5.2.1 增强 Motion Photo 结构分析与输出验证；v5.3.0 修复 Xiaomi Motion Photo 重复 EXIF 导致 HyperOS 无法识别的问题。

完整的逐条开发记录请参阅 [CHANGELOG.md](../CHANGELOG.md)。本文件用于后续维护者快速恢复项目上下文，不替代 Codex 中的完整对话记录。
